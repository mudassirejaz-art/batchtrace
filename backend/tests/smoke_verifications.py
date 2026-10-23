"""Step 11 local-only physical count/review integration smoke; creates isolated records, no deletes."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select, text, update

from app.db.session import AsyncSessionLocal, engine
from app.features.imports.model import InventorySnapshotRow
from app.features.organizations.membership_model import OrganizationMembership
from app.features.verifications.model import StockVerification, VerificationDecision
from app.main import app


async def expect(client, method, url, status, **kwargs):
    result = await client.request(method, url, **kwargs)
    assert result.status_code == status, (method, url, status, result.status_code, result.text)
    return result


async def register(client, suffix):
    email = f"verify-{suffix}@example.com"
    password = "VerificationLocalTest2026#"
    created = await expect(client, "POST", "/api/v1/auth/register", 201, json={
        "email": email, "password": password,
        "organization_name": f"Verify org {suffix}",
        "organization_slug": f"verify-org-{suffix}",
    })
    token = await expect(client, "POST", "/api/v1/auth/login", 200, json={
        "email": email, "password": password,
    })
    return (created.json()["organization_id"], created.json()["user_id"],
            {"Authorization": "Bearer " + token.json()["access_token"]})


async def new_lot(client, base, auth, supplier, product, label, expiry):
    result = await expect(client, "POST", base + "/lots", 201, headers=auth, json={
        "supplier_id": supplier, "product_id": product,
        "batch_number": label, "expiry_date": expiry.isoformat(),
    })
    return result.json()["id"]


async def import_one(client, base, auth, observed_on, label, expiry, quantity):
    blob = ("product_sku,supplier_code,batch_number,expiry_date,quantity\n"
            f"VER-SKU,VER-SUP,{label},{expiry.isoformat()},{quantity}\n").encode()
    form = {"observed_on": observed_on.isoformat()}
    file = {"file": ("verify.csv", blob, "text/csv")}
    preview = await expect(client, "POST", base + "/imports/preview", 200,
                           headers=auth, data=form, files=file)
    assert preview.json()["valid"], preview.text
    form["preview_fingerprint"] = preview.json()["fingerprint"]
    committed = await expect(client, "POST", base + "/imports/commit", 201,
                             headers=auth, data=form, files=file)
    return committed.json()["id"]


async def main():
    # Guard before any registration or writes.
    if engine.url.host not in {"127.0.0.1", "localhost", "::1"} or engine.url.database != "batchtrace_db":
        raise SystemExit("STOP: Only local batchtrace_db allowed")
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT current_database()")) == "batchtrace_db"
        revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision in {"b4d7f0c9e831", "c5e81d0a624f", "d6f20a718c43", "e7b54d260a91"}, ("Run step 11 migration before smoke", revision)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        suffix = uuid4().hex[:12]
        org_a, user_a, auth_a = await register(client, suffix + "a")
        org_b, user_b, auth_b = await register(client, suffix + "b")
        org_c, user_c, auth_c = await register(client, suffix + "c")
        base = f"/api/v1/organizations/{org_a}"
        endpoint = base + "/recovery/verifications"
        print("PASS: Local DB migration guard; three independent users/orgs")

        await expect(client, "GET", endpoint, 401)
        await expect(client, "GET", endpoint, 404, headers=auth_b)
        await expect(client, "GET", endpoint, 404, headers=auth_c)
        assert (await expect(client, "GET", endpoint, 200, headers=auth_a)).json() == []
        print("PASS: Anonymous and foreign organizations blocked")

        supplier = (await expect(client, "POST", base + "/suppliers", 201, headers=auth_a,
                                 json={"code": "VER-SUP", "name": "Verification supplier"})).json()["id"]
        product = (await expect(client, "POST", base + "/products", 201, headers=auth_a,
                                json={"sku": "VER-SKU", "name": "Verification product"})).json()["id"]
        today = datetime.now(timezone.utc).date()
        expiry = today + timedelta(days=12)
        policy = (await expect(client, "POST", base + "/return-policies", 201,
                               headers=auth_a, json={
            "supplier_id": supplier, "days_before_expiry": 45, "days_after_expiry": 15,
            "effective_from": (today - timedelta(days=5)).isoformat(),
        })).json()
        lot = await new_lot(client, base, auth_a, supplier, product, "A", expiry)
        source_import = await import_one(client, base, auth_a, today, "A", expiry, 25)
        print("PASS: Return-open lot, policy, and snapshot prepared")

        payload = {"lot_id": lot, "import_id": source_import,
                   "counted_quantity": 20, "note": "Counted twenty sealed cartons on location A."}
        key = {"Idempotency-Key": "verify-test-" + suffix}
        await expect(client, "POST", endpoint, 422, headers=auth_a, json=payload)
        await expect(client, "POST", endpoint, 401, headers=key, json=payload)
        await expect(client, "POST", endpoint, 404, headers={**auth_c, **key}, json=payload)
        await expect(client, "POST", endpoint, 409, headers={**auth_a, **key},
                     json={**payload, "import_id": str(uuid4())})
        await expect(client, "POST", endpoint, 422, headers={**auth_a, **key},
                     json={**payload, "counted_quantity": -1})
        print("PASS: Source freshness guard, request validation, authorization")

        verification = (await expect(client, "POST", endpoint, 201,
                                     headers={**auth_a, **key}, json=payload)).json()
        assert verification["status"] == "pending"
        assert verification["observed_quantity"] == 25
        assert verification["counted_quantity"] == 20
        assert verification["policy_id"] == policy["id"]
        assert verification["is_supplier_claim"] is False
        assert verification["changes_inventory_balance"] is False
        repeat = (await expect(client, "POST", endpoint, 201,
                               headers={**auth_a, **key}, json=payload)).json()
        assert repeat["id"] == verification["id"]
        await expect(client, "POST", endpoint, 409, headers={**auth_a, **key},
                     json={**payload, "counted_quantity": 21})
        await expect(client, "POST", endpoint, 409,
                     headers={**auth_a, "Idempotency-Key": "different-" + suffix}, json=payload)
        print("PASS: Atomic submit, idempotent retry, conflicting count rejected")

        await expect(client, "GET", endpoint + "/" + verification["id"], 200, headers=auth_a)
        await expect(client, "GET", endpoint + "/" + verification["id"], 404, headers=auth_c)
        assert len((await expect(client, "GET", endpoint, 200, headers=auth_a)).json()) == 1
        await expect(client, "GET", endpoint + "?limit=0", 422, headers=auth_a)
        print("PASS: Details, pagination and org-scoped reads")

        # Independent reviewer uses a second user with actual membership; make them viewer first.
        async with AsyncSessionLocal() as db:
            db.add(OrganizationMembership(
                organization_id=UUID(org_a), user_id=UUID(user_b), role="viewer",
            ))
            await db.commit()
        await expect(client, "GET", endpoint, 200, headers=auth_b)
        await expect(client, "POST", endpoint, 403, headers={**auth_b, **key}, json=payload)
        await expect(client, "POST", endpoint + "/" + verification["id"] + "/review", 403,
                     headers=auth_b, json={"decision": "approved", "reason": "Checked warehouse evidence"})
        await expect(client, "POST", endpoint + "/" + verification["id"] + "/review", 403,
                     headers=auth_a, json={"decision": "approved", "reason": "Checked warehouse evidence"})
        async with AsyncSessionLocal() as db:
            await db.execute(update(OrganizationMembership).where(
                OrganizationMembership.organization_id == UUID(org_a),
                OrganizationMembership.user_id == UUID(user_b),
            ).values(role="admin"))
            await db.commit()
        approved = (await expect(client, "POST", endpoint + "/" + verification["id"] + "/review", 200,
                                 headers=auth_b, json={"decision": "approved",
                                                      "reason": "Physical count cross-checked independently"})).json()
        assert approved["verification"]["status"] == "approved"
        assert approved["reviewed_by_user_id"] == user_b
        await expect(client, "POST", endpoint + "/" + verification["id"] + "/review", 409,
                     headers=auth_b, json={"decision": "rejected", "reason": "Repeated review attempt"})
        print("PASS: Viewer can read only; independent admin review; immutable single decision")

        # Updating a CSV source invalidates an unreviewed count for approval (but rejection is allowed).
        newer_lot = await new_lot(client, base, auth_a, supplier, product, "B", expiry)
        initial_import = await import_one(client, base, auth_a, today, "B", expiry, 40)
        another_payload = {"lot_id": newer_lot, "import_id": initial_import,
                           "counted_quantity": 35, "note": "Physical count thirty five cartons on shelf B."}
        other = (await expect(client, "POST", endpoint, 201,
                              headers={**auth_a, "Idempotency-Key": "second-" + suffix},
                              json=another_payload)).json()
        latest_import = await import_one(client, base, auth_a, today, "B", expiry, 44)
        assert latest_import != initial_import
        await expect(client, "POST", endpoint + "/" + other["id"] + "/review", 409,
                     headers=auth_b, json={"decision": "approved", "reason": "I reviewed the warehouse count"})
        rejected = (await expect(client, "POST", endpoint + "/" + other["id"] + "/review", 200,
                                 headers=auth_b, json={"decision": "rejected",
                                                      "reason": "Source changed; warehouse must recount"})).json()
        assert rejected["verification"]["status"] == "rejected"
        print("PASS: Superseded source blocks approval; rejection is auditable")

        concurrent_lot = await new_lot(client, base, auth_a, supplier, product, "C", expiry)
        concurrent_import = await import_one(client, base, auth_a, today, "C", expiry, 75)
        parallel = {"lot_id": concurrent_lot, "import_id": concurrent_import,
                    "counted_quantity": 71, "note": "Recounted seventy one cartons before submission."}
        results = await asyncio.gather(
            client.post(endpoint, headers={**auth_a, "Idempotency-Key": "race-a-" + suffix}, json=parallel),
            client.post(endpoint, headers={**auth_a, "Idempotency-Key": "race-b-" + suffix}, json=parallel),
        )
        assert sorted(x.status_code for x in results) == [201, 409], [(x.status_code, x.text) for x in results]
        print("PASS: Concurrent submission race produces one verification only")

        async with AsyncSessionLocal() as db:
            count = await db.scalar(select(func.count()).select_from(StockVerification).where(
                StockVerification.organization_id == UUID(org_a)))
            decisions = await db.scalar(select(func.count()).select_from(VerificationDecision))
            immutable_source = await db.scalar(select(InventorySnapshotRow.observed_quantity).where(
                InventorySnapshotRow.id == UUID(verification["snapshot_row_id"])))
        assert count == 3 and decisions >= 2 and immutable_source == 25, (count, decisions, immutable_source)
        print("PASS: Exactly three verified submissions; original observed quantity unchanged")
        print("PASS: Step 11 verification + independent review integration smoke completed")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
