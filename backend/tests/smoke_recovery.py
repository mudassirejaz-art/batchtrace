"""Step 10 local-only end-to-end checks. Creates isolated test data; no deletes."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import httpx
from sqlalchemy import select, text, update, func

from app.db.session import AsyncSessionLocal, engine
from app.features.imports.model import InventoryImport, InventorySnapshotRow
from app.features.organizations.membership_model import OrganizationMembership
from app.main import app


async def expect(client, method, url, expected, **kwargs):
    response = await client.request(method, url, **kwargs)
    assert response.status_code == expected, (
        method, url, expected, response.status_code, response.text,
    )
    return response


async def register(client, name):
    email = f"recovery-{name}@example.com"
    password = "RecoveryTest2026#Password"
    result = await expect(client, "POST", "/api/v1/auth/register", 201, json={
        "email": email, "password": password,
        "organization_name": f"Recovery org {name}",
        "organization_slug": f"recovery-org-{name}",
    })
    login = await expect(client, "POST", "/api/v1/auth/login", 200, json={
        "email": email, "password": password,
    })
    return (
        result.json()["organization_id"], result.json()["user_id"],
        {"Authorization": "Bearer " + login.json()["access_token"]},
    )


async def make_supplier(client, base, auth, code):
    response = await expect(client, "POST", base + "/suppliers", 201, headers=auth, json={
        "code": code, "name": "Recovery supplier " + code,
    })
    return response.json()["id"]


async def make_product(client, base, auth, sku):
    response = await expect(client, "POST", base + "/products", 201, headers=auth, json={
        "sku": sku, "name": "Recovery product " + sku,
    })
    return response.json()["id"]


async def make_lot(client, base, auth, product_id, supplier_id, label, expiry):
    response = await expect(client, "POST", base + "/lots", 201, headers=auth, json={
        "product_id": product_id, "supplier_id": supplier_id,
        "batch_number": label, "expiry_date": expiry.isoformat(),
    })
    return response.json()["id"]


async def make_policy(client, base, auth, supplier_id, start, before=45, after=15, end=None):
    response = await expect(client, "POST", base + "/return-policies", 201,
                            headers=auth, json={
        "supplier_id": supplier_id,
        "days_before_expiry": before, "days_after_expiry": after,
        "effective_from": start.isoformat(),
        "effective_to": end.isoformat() if end else None,
    })
    return response.json()


def csv_for(entries):
    header = "product_sku,supplier_code,batch_number,expiry_date,quantity\n"
    data = "\n".join(
        f"{sku},{code},{batch},{expires.isoformat()},{quantity}"
        for sku, code, batch, expires, quantity in entries
    )
    return (header + data + "\n").encode("utf-8")


async def import_snapshot(client, base, auth, observed_on, entries):
    blob = csv_for(entries)
    data = {"observed_on": observed_on.isoformat()}
    files = {"file": ("recovery.csv", blob, "text/csv")}
    preview = await expect(client, "POST", base + "/imports/preview", 200,
                           headers=auth, data=data, files=files)
    value = preview.json()
    assert value["valid"], value
    data["preview_fingerprint"] = value["fingerprint"]
    imported = await expect(client, "POST", base + "/imports/commit", 201,
                            headers=auth, data=data, files=files)
    return imported.json()["id"]


async def main():
    # The guard happens before any write operations, including auth registration.
    if engine.url.host not in {"127.0.0.1", "localhost", "::1"} or engine.url.database != "batchtrace_db":
        raise SystemExit("STOP: Only localhost batchtrace_db is allowed")
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT current_database()")) == "batchtrace_db"
        revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision in {"a7e65ca94f10", "b4d7f0c9e831", "c5e81d0a624f", "d6f20a718c43", "e7b54d260a91"}, ("Expected Step 9+ database revision", revision)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        suffix = uuid4().hex[:12]
        org_a, user_a, auth_a = await register(client, suffix + "a")
        org_b, _, auth_b = await register(client, suffix + "b")
        base_a = f"/api/v1/organizations/{org_a}"
        base_b = f"/api/v1/organizations/{org_b}"
        recovery_a = base_a + "/recovery/opportunities"
        recovery_b = base_b + "/recovery/opportunities"
        today = datetime.now(timezone.utc).date()
        old = today - timedelta(days=10)
        print("PASS: Local DB guard, two isolated organizations")

        await expect(client, "GET", recovery_a, 401)
        await expect(client, "GET", recovery_a, 404, headers=auth_b)
        assert (await expect(client, "GET", recovery_a, 200, headers=auth_a)).json() == []
        print("PASS: Anonymous blocked, foreign organization concealed, empty initial view")

        sku, code = "REC-SKU", "REC-SUP"
        product = await make_product(client, base_a, auth_a, sku)
        supplier = await make_supplier(client, base_a, auth_a, code)
        no_policy_supplier = await make_supplier(client, base_a, auth_a, "REC-NOP")
        expired_policy_supplier = await make_supplier(client, base_a, auth_a, "REC-EXP")
        foreign_product = await make_product(client, base_b, auth_b, "B-REC")
        foreign_supplier = await make_supplier(client, base_b, auth_b, "B-SUP")
        expiry = {
            "MAIN": today + timedelta(days=20),
            "ZERO": today + timedelta(days=10),
            "STALE": today + timedelta(days=14),
            "FUTURE": today + timedelta(days=80),
            "CLOSED": today - timedelta(days=30),
            "NOPOL": today + timedelta(days=8),
            "POLEXP": today + timedelta(days=8),
            "UNSEEN": today + timedelta(days=18),
        }
        lot_ids = {}
        for label, exp in expiry.items():
            owner_supplier = (
                no_policy_supplier if label == "NOPOL" else
                expired_policy_supplier if label == "POLEXP" else supplier
            )
            lot_ids[label] = await make_lot(client, base_a, auth_a, product,
                                            owner_supplier, label, exp)
        foreign_lot_expiry = today + timedelta(days=5)
        await make_lot(client, base_b, auth_b, foreign_product, foreign_supplier,
                       "FOREIGN", foreign_lot_expiry)
        print("PASS: Organization-scoped product, suppliers and test lots created")

        first = await make_policy(client, base_a, auth_a, supplier,
                                  today - timedelta(days=100), before=5, after=15)
        second = await make_policy(client, base_a, auth_a, supplier,
                                   today - timedelta(days=1), before=45, after=15)
        assert first["version"] == 1 and second["version"] == 2
        expired = await make_policy(client, base_a, auth_a, expired_policy_supplier,
                                    today - timedelta(days=100), before=45, after=15,
                                    end=today - timedelta(days=1))
        assert expired["version"] == 1
        print("PASS: Supplier policies versioned, including expired policy")

        # Older observation first, latest observation second.
        old_id = await import_snapshot(client, base_a, auth_a, old, [
            (sku, code, "MAIN", expiry["MAIN"], 100),
            (sku, code, "STALE", expiry["STALE"], 5),
        ])
        current_id = await import_snapshot(client, base_a, auth_a, today, [
            (sku, code, "MAIN", expiry["MAIN"], 8),
            (sku, code, "ZERO", expiry["ZERO"], 0),
            (sku, code, "FUTURE", expiry["FUTURE"], 11),
            (sku, code, "CLOSED", expiry["CLOSED"], 4),
            (sku, "REC-NOP", "NOPOL", expiry["NOPOL"], 6),
            (sku, "REC-EXP", "POLEXP", expiry["POLEXP"], 7),
        ])
        # Backdated CSV imported AFTER current day must not supersede newer observation.
        await import_snapshot(client, base_a, auth_a, today - timedelta(days=20), [
            (sku, code, "MAIN", expiry["MAIN"], 500),
        ])
        foreign_id = await import_snapshot(client, base_b, auth_b, today, [
            ("B-REC", "B-SUP", "FOREIGN", foreign_lot_expiry, 333),
        ])
        print("PASS: Current, historical, later-uploaded older, and foreign observations")

        result = (await expect(client, "GET", recovery_a, 200, headers=auth_a)).json()
        by_label = {entry["batch_number"]: entry for entry in result}
        assert len(result) == 7, (len(result), list(by_label))
        assert "UNSEEN" not in by_label and "FOREIGN" not in by_label
        assert len({entry["lot_id"] for entry in result}) == len(result)
        assert by_label["MAIN"]["observed_quantity"] == 8
        assert by_label["MAIN"]["import_id"] == current_id
        assert by_label["MAIN"]["opportunity_status"] == "verify_stock"
        assert by_label["MAIN"]["date_window_status"] == "window_open"
        assert by_label["MAIN"]["policy_version"] == 2
        assert by_label["MAIN"]["return_opens_on"] == (expiry["MAIN"] - timedelta(days=45)).isoformat()
        assert by_label["MAIN"]["return_closes_on"] == (expiry["MAIN"] + timedelta(days=15)).isoformat()
        assert by_label["MAIN"]["snapshot_is_stale"] is False
        assert by_label["ZERO"]["opportunity_status"] == "zero_observed"
        assert by_label["STALE"]["opportunity_status"] == "stale_snapshot"
        assert by_label["STALE"]["snapshot_age_days"] == 10
        assert by_label["FUTURE"]["opportunity_status"] == "not_yet_open"
        assert by_label["CLOSED"]["opportunity_status"] == "window_closed"
        assert by_label["NOPOL"]["opportunity_status"] == "no_policy"
        assert by_label["POLEXP"]["opportunity_status"] == "policy_expired"
        assert all(x["requires_physical_verification"] is True for x in result)
        assert all(x["authoritative_inventory"] is False and
                   x["supplier_claim_approved"] is False for x in result)
        assert all(x["observed_quantity"] != 333 for x in result)
        print("PASS: Seven explainable statuses, source provenance and unverified labels")

        historical = (await expect(client, "GET", recovery_a, 200, headers=auth_a,
                                   params={"as_of": old.isoformat()})).json()
        hist = {x["batch_number"]: x for x in historical}
        assert set(hist) == {"MAIN", "STALE"}, hist
        assert hist["MAIN"]["observed_quantity"] == 100
        assert hist["MAIN"]["import_id"] == old_id
        assert hist["MAIN"]["policy_version"] == 1
        assert hist["MAIN"]["opportunity_status"] == "not_yet_open"
        print("PASS: Historical observed_on and effective policy version, no future snapshots")

        nonstale = (await expect(client, "GET", recovery_a, 200, headers=auth_a,
                                 params={"max_snapshot_age_days": 15})).json()
        assert {x["batch_number"]: x for x in nonstale}["STALE"]["opportunity_status"] == "verify_stock"
        assert len((await expect(client, "GET", recovery_a, 200, headers=auth_a,
                                 params={"supplier_id": str(no_policy_supplier)})).json()) == 1
        assert len((await expect(client, "GET", recovery_a, 200, headers=auth_a,
                                 params={"product_id": str(product)})).json()) == 7
        first_page = (await expect(client, "GET", recovery_a, 200, headers=auth_a,
                                   params={"limit": 2, "offset": 0})).json()
        next_page = (await expect(client, "GET", recovery_a, 200, headers=auth_a,
                                  params={"limit": 2, "offset": 2})).json()
        assert len(first_page) == len(next_page) == 2
        assert set(x["lot_id"] for x in first_page).isdisjoint({x["lot_id"] for x in next_page})
        await expect(client, "GET", recovery_a + "?limit=0", 422, headers=auth_a)
        await expect(client, "GET", recovery_a + "?max_snapshot_age_days=-1", 422, headers=auth_a)
        print("PASS: Age threshold, filters, deterministic pagination, invalid query validation")

        visible_b = (await expect(client, "GET", recovery_b, 200, headers=auth_b)).json()
        assert len(visible_b) == 1 and visible_b[0]["batch_number"] == "FOREIGN"
        assert visible_b[0]["import_id"] == foreign_id
        await expect(client, "GET", recovery_b, 404, headers=auth_a)
        print("PASS: Both-way tenant isolation and foreign data not exposed")

        async with AsyncSessionLocal() as db:
            before_imports = await db.scalar(select(func.count()).select_from(InventoryImport).where(
                InventoryImport.organization_id == org_a
            ))
            before_rows = await db.scalar(select(func.count()).select_from(InventorySnapshotRow).join(
                InventoryImport, InventorySnapshotRow.import_id == InventoryImport.id
            ).where(InventoryImport.organization_id == org_a))
            await db.execute(update(OrganizationMembership).where(
                OrganizationMembership.user_id == user_a,
                OrganizationMembership.organization_id == org_a,
            ).values(role="viewer"))
            await db.commit()
        await expect(client, "GET", recovery_a, 200, headers=auth_a)
        async with AsyncSessionLocal() as db:
            after_imports = await db.scalar(select(func.count()).select_from(InventoryImport).where(
                InventoryImport.organization_id == org_a
            ))
            after_rows = await db.scalar(select(func.count()).select_from(InventorySnapshotRow).join(
                InventoryImport, InventorySnapshotRow.import_id == InventoryImport.id
            ).where(InventoryImport.organization_id == org_a))
        assert (before_imports, before_rows) == (after_imports, after_rows)
        assert (before_imports, before_rows) == (3, 9)
        print("PASS: Viewer read-only, no inventory snapshot writes on GET")

    print("PASS: Step 10 recovery opportunity integration smoke completed")


if __name__ == "__main__":
    asyncio.run(main())
