"""Step 8 integration smoke. Local batchtrace_db only, creates unique test data, no delete."""
import asyncio
from datetime import date, timedelta
from uuid import uuid4

import httpx
from sqlalchemy import text, update

from app.db.session import AsyncSessionLocal, engine
from app.features.organizations.membership_model import OrganizationMembership
from app.main import app


async def expect(client, method, url, code, **kwargs):
    r = await client.request(method, url, **kwargs)
    assert r.status_code == code, (method, url, code, r.status_code, r.text)
    return r


async def register(client, suffix):
    email = f"policy-smoke-{suffix}@example.com"
    password = "LocalPolicySmokeTest2026!"
    r = await expect(client, "POST", "/api/v1/auth/register", 201, json={
        "email": email, "password": password,
        "organization_name": f"Policy smoke {suffix}",
        "organization_slug": f"policy-smoke-{suffix}",
    })
    token = await expect(client, "POST", "/api/v1/auth/login", 200,
                         json={"email": email, "password": password})
    return (r.json()["organization_id"], r.json()["user_id"],
            {"Authorization": "Bearer " + token.json()["access_token"]})


async def main():
    # Guard checked BEFORE any registration or writes.
    if engine.url.host not in {"127.0.0.1", "localhost", "::1"} or engine.url.database != "batchtrace_db":
        raise SystemExit("STOP: Only localhost batchtrace_db is allowed")
    async with engine.connect() as conn:
        db = await conn.scalar(text("SELECT current_database()"))
        assert db == "batchtrace_db", db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        suffix = uuid4().hex[:12]
        org_a, user_a, auth_a = await register(client, suffix + "a")
        org_b, _, auth_b = await register(client, suffix + "b")
        pa = f"/api/v1/organizations/{org_a}"
        pb = f"/api/v1/organizations/{org_b}"
        policies = pa + "/return-policies"
        policies_b = pb + "/return-policies"
        print("PASS: Two separate organizations and JWTs")

        await expect(client, "GET", policies, 401)
        await expect(client, "POST", policies, 401, json={})
        await expect(client, "GET", policies, 404, headers=auth_b)
        print("PASS: Anonymous and cross-organization access denied")

        supp_a = (await expect(client, "POST", pa + "/suppliers", 201, headers=auth_a,
                               json={"code": "POL-SUP", "name": "Policy supplier"})).json()["id"]
        supp_b = (await expect(client, "POST", pb + "/suppliers", 201, headers=auth_b,
                               json={"code": "POL-SUP", "name": "Different supplier"})).json()["id"]
        product = (await expect(client, "POST", pa + "/products", 201, headers=auth_a,
                               json={"sku": "POL-PRD", "name": "Policy product"})).json()["id"]
        anchor = date(2026, 5, 15)
        expiry = anchor + timedelta(days=30)
        lot = (await expect(client, "POST", pa + "/lots", 201, headers=auth_a,
                            json={"product_id": product, "supplier_id": supp_a,
                                  "batch_number": "POL-BATCH", "expiry_date": expiry.isoformat()})).json()["id"]
        evaluate = pa + f"/lots/{lot}/return-window"
        print("PASS: Supplier, product and lot prerequisites")

        no_policy = await expect(client, "GET", evaluate, 200, headers=auth_a,
                                 params={"as_of": anchor.isoformat()})
        assert no_policy.json()["status"] == "no_policy"
        assert no_policy.json()["date_window_only"] is True
        await expect(client, "GET", pb + f"/lots/{lot}/return-window", 404, headers=auth_b)
        await expect(client, "GET", evaluate, 404, headers=auth_b)
        print("PASS: No-policy status and cross-organization lot isolation")

        initial = {"supplier_id": supp_a, "days_before_expiry": 45,
                   "days_after_expiry": 15,
                   "effective_from": (anchor - timedelta(days=20)).isoformat(),
                   "effective_to": (anchor + timedelta(days=100)).isoformat()}
        first = (await expect(client, "POST", policies, 201, headers=auth_a, json=initial)).json()
        assert first["version"] == 1 and first["organization_id"] == org_a
        r = await expect(client, "GET", evaluate, 200, headers=auth_a,
                         params={"as_of": anchor.isoformat()})
        assert r.json()["status"] == "window_open", r.text
        assert r.json()["policy_version"] == 1
        assert r.json()["return_opens_on"] == (expiry - timedelta(days=45)).isoformat()
        assert r.json()["return_closes_on"] == (expiry + timedelta(days=15)).isoformat()
        r = await expect(client, "GET", evaluate, 200, headers=auth_a,
                         params={"as_of": (anchor - timedelta(days=21)).isoformat()})
        assert r.json()["status"] == "no_policy"
        print("PASS: Version 1, exact date-window boundaries and effective-from guard")

        await expect(client, "POST", policies, 404, headers=auth_a,
                     json={**initial, "supplier_id": supp_b})
        await expect(client, "POST", policies, 422, headers=auth_a,
                     json={**initial, "days_before_expiry": -1})
        await expect(client, "POST", policies, 422, headers=auth_a,
                     json={**initial, "days_after_expiry": 3651})
        await expect(client, "POST", policies, 422, headers=auth_a,
                     json={**initial, "effective_to": (anchor - timedelta(days=21)).isoformat()})
        await expect(client, "POST", policies, 422, headers=auth_a,
                     json={**initial, "version": 999})
        await expect(client, "POST", policies, 409, headers=auth_a, json=initial)
        print("PASS: Schema validation, supplier scope and monotonic version start")

        second_payload = {**initial, "days_before_expiry": 3,
                          "days_after_expiry": 1,
                          "effective_from": (anchor + timedelta(days=10)).isoformat(),
                          "effective_to": (anchor + timedelta(days=45)).isoformat()}
        second = (await expect(client, "POST", policies, 201, headers=auth_a,
                               json=second_payload)).json()
        assert second["version"] == 2
        r = await expect(client, "GET", evaluate, 200, headers=auth_a,
                         params={"as_of": (anchor + timedelta(days=9)).isoformat()})
        assert r.json()["policy_version"] == 1 and r.json()["status"] == "window_open"
        expectations = [(10, "not_yet_open"), (27, "window_open"),
                        (31, "window_open"), (32, "window_closed"), (46, "policy_expired")]
        for days, expected in expectations:
            r = await expect(client, "GET", evaluate, 200, headers=auth_a,
                             params={"as_of": (anchor + timedelta(days=days)).isoformat()})
            assert r.json()["status"] == expected, (days, r.text)
            assert r.json()["policy_version"] == 2
        print("PASS: Version 2 supersedes old rule, statuses and expiry")

        history = await expect(client, "GET", policies, 200, headers=auth_a,
                               params={"supplier_id": supp_a})
        assert [x["version"] for x in history.json()] == [2, 1], history.text
        await expect(client, "GET", policies + "/" + first["id"], 200, headers=auth_a)
        await expect(client, "GET", policies_b + "/" + first["id"], 404, headers=auth_b)
        await expect(client, "GET", policies + "?limit=0", 422, headers=auth_a)
        await expect(client, "POST", policies_b, 404, headers=auth_b, json=second_payload)
        print("PASS: Append-only policy history, read isolation and query validation")

        # Concurrent requests for the same effective_from must serialize on the supplier.
        simultaneous = {**second_payload,
                        "effective_from": (anchor + timedelta(days=50)).isoformat(),
                        "effective_to": (anchor + timedelta(days=85)).isoformat()}
        results = await asyncio.gather(
            client.post(policies, json=simultaneous, headers=auth_a),
            client.post(policies, json=simultaneous, headers=auth_a),
        )
        assert sorted(r.status_code for r in results) == [201, 409], [
            (r.status_code, r.text) for r in results
        ]
        created = next(r for r in results if r.status_code == 201).json()
        assert created["version"] == 3
        print("PASS: Concurrent same-date version writes yield one 201 and one 409")

        # Modify only this test-owned user's membership, never other data.
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(OrganizationMembership).where(
                    OrganizationMembership.organization_id == org_a,
                    OrganizationMembership.user_id == user_a,
                ).values(role="viewer")
            )
            await db.commit()
        await expect(client, "GET", evaluate, 200, headers=auth_a,
                     params={"as_of": anchor.isoformat()})
        await expect(client, "GET", policies, 200, headers=auth_a)
        await expect(client, "POST", policies, 403, headers=auth_a,
                     json={**second_payload, "effective_from": (anchor + timedelta(days=50)).isoformat()})
        print("PASS: Viewer allowed to read, blocked from write")

    await engine.dispose()
    print("PASS: Step 8 supplier policy integration smoke completed")


if __name__ == "__main__":
    asyncio.run(main())
