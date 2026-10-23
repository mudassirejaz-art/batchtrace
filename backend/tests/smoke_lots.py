"""Step 7 local DB integration smoke; creates isolated records, never deletes them.

Usage: PYTHONPATH="$PWD" python tests/smoke_lots.py
Test uses ASGITransport only, without any third-party API or HTTP network calls.
"""
import asyncio
from datetime import datetime, timedelta, timezone
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


async def register(client, unique):
    email = f"lot-smoke-{unique}@example.com"
    password = "LocalLotsSmokeTest2026!"
    r = await expect(client, "POST", "/api/v1/auth/register", 201, json={
        "email": email,
        "password": password,
        "organization_name": f"Lot smoke {unique}",
        "organization_slug": f"lot-smoke-{unique}",
    })
    login = await expect(client, "POST", "/api/v1/auth/login", 200, json={
        "email": email, "password": password,
    })
    return (
        r.json()["organization_id"],
        r.json()["user_id"],
        {"Authorization": f"Bearer {login.json()['access_token']}"},
    )


async def main():
    if (engine.url.host not in {"localhost", "127.0.0.1", "::1"}
            or engine.url.database != "batchtrace_db"):
        raise SystemExit("STOP: Only local batchtrace_db is allowed")
    async with engine.connect() as conn:
        db_name = await conn.scalar(text("SELECT current_database()"))
        assert db_name == "batchtrace_db", db_name

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique = uuid4().hex[:12]
        org_a, user_a, auth_a = await register(client, unique + "a")
        org_b, _, auth_b = await register(client, unique + "b")
        path_a = f"/api/v1/organizations/{org_a}"
        path_b = f"/api/v1/organizations/{org_b}"
        lots_a = path_a + "/lots"
        lots_b = path_b + "/lots"
        print("PASS: Two independently authorized test organizations")

        await expect(client, "GET", lots_a, 401)
        await expect(client, "POST", lots_a, 401, json={})
        print("PASS: Anonymous access rejected")

        sa = await expect(client, "POST", path_a + "/suppliers", 201,
                          headers=auth_a, json={"code": "LT-SUP", "name": "Batch supplier"})
        pa = await expect(client, "POST", path_a + "/products", 201,
                          headers=auth_a, json={"sku": "LT-SKU", "name": "Batch product"})
        sb = await expect(client, "POST", path_b + "/suppliers", 201,
                          headers=auth_b, json={"code": "LT-SUP", "name": "Other supplier"})
        pb = await expect(client, "POST", path_b + "/products", 201,
                          headers=auth_b, json={"sku": "LT-SKU", "name": "Other product"})
        sid, pid = sa.json()["id"], pa.json()["id"]
        sid_b, pid_b = sb.json()["id"], pb.json()["id"]
        print("PASS: Supplier/product prerequisites created")

        today = datetime.now(timezone.utc).date()
        async def new_lot(batch, expiry, *, supplier=sid, product=pid, org=lots_a, headers=auth_a):
            return await expect(client, "POST", org, 201, headers=headers, json={
                "supplier_id": supplier,
                "product_id": product,
                "batch_number": batch,
                "expiry_date": expiry.isoformat(),
            })

        past = await new_lot("past", today - timedelta(days=2))
        due = await new_lot("  due  ", today)
        soon = await new_lot("soon", today + timedelta(days=8))
        distant = await new_lot("later", today + timedelta(days=90))
        assert due.json()["batch_number"] == "DUE"
        print("PASS: Past, today, soon and future lot dates stored")

        await expect(client, "POST", lots_a, 409, headers=auth_a, json={
            "supplier_id": sid, "product_id": pid,
            "batch_number": "due", "expiry_date": today.isoformat(),
        })
        await expect(client, "POST", lots_a, 422, headers=auth_a, json={
            "supplier_id": sid, "product_id": pid,
            "batch_number": "  ", "expiry_date": today.isoformat(),
        })
        await expect(client, "POST", lots_a, 422, headers=auth_a, json={
            "supplier_id": sid, "product_id": pid,
            "batch_number": "new", "expiry_date": today.isoformat(),
            "organization_id": org_b,
        })
        print("PASS: Duplicate lot and invalid payloads rejected")

        await expect(client, "POST", lots_a, 404, headers=auth_a, json={
            "supplier_id": sid_b, "product_id": pid,
            "batch_number": "wrong-supplier", "expiry_date": today.isoformat(),
        })
        await expect(client, "POST", lots_a, 404, headers=auth_a, json={
            "supplier_id": sid, "product_id": pid_b,
            "batch_number": "wrong-product", "expiry_date": today.isoformat(),
        })
        await expect(client, "GET", lots_b + "/" + due.json()["id"], 404, headers=auth_b)
        await expect(client, "GET", lots_a, 404, headers=auth_b)
        await expect(client, "GET", lots_a + "/expiry-watch", 404, headers=auth_b)
        await expect(client, "POST", lots_a, 404, headers=auth_b, json={
            "supplier_id": sid, "product_id": pid,
            "batch_number": "DENIED", "expiry_date": today.isoformat(),
        })
        other_org_lot = await new_lot(
            "DUE", today, supplier=sid_b, product=pid_b,
            org=lots_b, headers=auth_b,
        )
        assert other_org_lot.json()["organization_id"] == org_b
        print("PASS: Cross-organization references and access rejected")
        print("PASS: Same lot label permitted in separate organizations")

        all_lots = await expect(client, "GET", lots_a, 200, headers=auth_a)
        assert len(all_lots.json()) == 4
        only_product = await expect(
            client, "GET", lots_a + f"?product_id={pid}", 200, headers=auth_a
        )
        assert len(only_product.json()) == 4
        only_supplier = await expect(
            client, "GET", lots_a + f"?supplier_id={sid_b}", 200, headers=auth_a
        )
        assert only_supplier.json() == []
        await expect(client, "GET", lots_a + "/" + due.json()["id"], 200, headers=auth_a)
        await expect(client, "GET", lots_a + "?limit=0", 422, headers=auth_a)
        print("PASS: Detail, filters, paging and organization-scoped reads")

        watch = await expect(
            client, "GET", lots_a + "/expiry-watch", 200, headers=auth_a,
            params={"within_days": 30, "as_of": today.isoformat()},
        )
        items = watch.json()
        assert [i["id"] for i in items] == [due.json()["id"], soon.json()["id"]], items
        assert items[0]["days_until_expiry"] == 0 and items[0]["urgency"] == "due_today"
        assert items[1]["days_until_expiry"] == 8 and items[1]["urgency"] == "upcoming"
        only_due = await expect(
            client, "GET", lots_a + "/expiry-watch", 200, headers=auth_a,
            params={"within_days": 0, "as_of": today.isoformat()},
        )
        assert [i["id"] for i in only_due.json()] == [due.json()["id"]]
        await expect(client, "GET", lots_a + "/expiry-watch?within_days=-1", 422, headers=auth_a)
        await expect(client, "GET", lots_a + "/expiry-watch?within_days=366", 422, headers=auth_a)
        print("PASS: Expiry windows, boundary dates, ordering, and validation")

        # Alter only THIS test's unique membership to check role permissions.
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(OrganizationMembership)
                .where(OrganizationMembership.organization_id == org_a)
                .where(OrganizationMembership.user_id == user_a)
                .values(role="viewer")
            )
            await db.commit()
        await expect(client, "GET", lots_a, 200, headers=auth_a)
        await expect(client, "GET", lots_a + "/expiry-watch", 200, headers=auth_a)
        await expect(client, "POST", lots_a, 403, headers=auth_a, json={
            "supplier_id": sid, "product_id": pid,
            "batch_number": "VIEWER", "expiry_date": today.isoformat(),
        })
        print("PASS: Viewer read-only restrictions")

    await engine.dispose()
    print("PASS: Step 7 lot/expiry smoke completed")


if __name__ == "__main__":
    asyncio.run(main())
