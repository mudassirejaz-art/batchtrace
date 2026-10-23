"""Local-only PostgreSQL integration smoke for Step 9.

Creates uniquely named orgs and immutable test snapshots; does not delete records.
"""
import asyncio
from datetime import date, timedelta, timezone, datetime
from uuid import uuid4

import httpx
from sqlalchemy import select, text, update

from app.db.session import AsyncSessionLocal, engine
from app.features.imports.model import InventoryImport, InventorySnapshotRow
from app.features.organizations.membership_model import OrganizationMembership
from app.main import app


async def expect(client, method, url, status, **kwargs):
    response = await client.request(method, url, **kwargs)
    assert response.status_code == status, (method, url, status, response.status_code, response.text)
    return response


async def register(client, name):
    password = "LocalSnapshotIntegration2026!"
    email = f"snapshot-{name}@example.com"
    res = await expect(client, "POST", "/api/v1/auth/register", 201, json={
        "email": email, "password": password,
        "organization_name": f"Snapshot smoke {name}",
        "organization_slug": f"snapshot-smoke-{name}",
    })
    token = await expect(client, "POST", "/api/v1/auth/login", 200,
                         json={"email": email, "password": password})
    return (res.json()["organization_id"], res.json()["user_id"],
            {"Authorization": "Bearer " + token.json()["access_token"]})


def sample_csv(rows):
    return ("product_sku,supplier_code,batch_number,expiry_date,quantity\n" +
            "\n".join(rows) + "\n").encode("utf-8")


def form_file(blob, *, observed=None, fingerprint=None):
    values = {"observed_on": (observed or date.today()).isoformat()}
    if fingerprint is not None:
        values["preview_fingerprint"] = fingerprint
    return {"data": values, "files": {"file": ("stock.csv", blob, "text/csv")}}


async def main():
    # Guard BEFORE all write operations (including registration).
    if engine.url.host not in {"127.0.0.1", "localhost", "::1"} or engine.url.database != "batchtrace_db":
        raise SystemExit("STOP: Only localhost batchtrace_db is allowed")
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT current_database()")) == "batchtrace_db"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        suffix = uuid4().hex[:12]
        org_a, user_a, auth_a = await register(client, suffix + "a")
        org_b, _, auth_b = await register(client, suffix + "b")
        pa, pb = f"/api/v1/organizations/{org_a}", f"/api/v1/organizations/{org_b}"
        imports_a, imports_b = pa + "/imports", pb + "/imports"
        today = datetime.now(timezone.utc).date()
        print("PASS: Local DB guard + two isolated organizations")

        await expect(client, "GET", imports_a, 401)
        await expect(client, "GET", imports_a, 404, headers=auth_b)
        await expect(client, "POST", imports_a + "/preview", 401, **form_file(b"x"))
        await expect(client, "POST", imports_a + "/commit", 404, headers=auth_b,
                     **form_file(b"x", fingerprint="0" * 64))
        print("PASS: Anonymous and cross-organization API access blocked")

        supplier = (await expect(client, "POST", pa + "/suppliers", 201, headers=auth_a,
                                 json={"code": "SNAP-SUP", "name": "Snapshot supplier"})).json()["id"]
        product = (await expect(client, "POST", pa + "/products", 201, headers=auth_a,
                                json={"sku": "SNAP-SKU", "name": "Snapshot product"})).json()["id"]
        other_supplier = (await expect(client, "POST", pb + "/suppliers", 201, headers=auth_b,
                                       json={"code": "B-SUP", "name": "B supplier"})).json()["id"]
        other_product = (await expect(client, "POST", pb + "/products", 201, headers=auth_b,
                                      json={"sku": "B-SKU", "name": "B product"})).json()["id"]
        expiry = today + timedelta(days=60)
        lot_ids = []
        for batch in ["ONE", "TWO"]:
            lot = await expect(client, "POST", pa + "/lots", 201, headers=auth_a,
                               json={"product_id": product, "supplier_id": supplier,
                                     "batch_number": batch, "expiry_date": expiry.isoformat()})
            lot_ids.append(lot.json()["id"])
        await expect(client, "POST", pb + "/lots", 201, headers=auth_b,
                     json={"product_id": other_product, "supplier_id": other_supplier,
                           "batch_number": "FOREIGN", "expiry_date": expiry.isoformat()})
        print("PASS: Products, suppliers and lots prepared")

        header = "SNAP-SKU,SNAP-SUP,"
        csv_data = sample_csv([
            f"{header}ONE,{expiry.isoformat()},100",
            f"{header}TWO,{expiry.isoformat()},0",
        ])
        preview = (await expect(client, "POST", imports_a + "/preview", 200,
                                headers=auth_a, **form_file(csv_data, observed=today))).json()
        assert preview["valid"] and preview["total_rows"] == 2 and preview["valid_rows"] == 2, preview
        assert preview["fingerprint"] and preview["snapshot_only"] is True
        current = await expect(client, "GET", imports_a, 200, headers=auth_a)
        assert current.json() == []
        print("PASS: Preview validates two rows without creating an import")

        invalid = sample_csv([
            f"SNAP-SKU,SNAP-SUP,ONE,{expiry.isoformat()},3",
            f"UNKNOWN,SNAP-SUP,THREE,{expiry.isoformat()},3",
            f"SNAP-SKU,SNAP-SUP,ONE,{expiry.isoformat()},3",
            f"B-SKU,B-SUP,FOREIGN,{expiry.isoformat()},3",
        ])
        result = (await expect(client, "POST", imports_a + "/preview", 200, headers=auth_a,
                               **form_file(invalid, observed=today))).json()
        assert not result["valid"] and result["fingerprint"] is None, result
        assert {"unknown_product", "duplicate_row"}.issubset({e["code"] for e in result["errors"]})
        await expect(client, "POST", imports_a + "/commit", 422, headers=auth_a,
                     **form_file(invalid, observed=today, fingerprint="0" * 64))
        await expect(client, "POST", imports_a + "/preview", 422, headers=auth_a,
                     **form_file(b"a,b\n1,2\n", observed=today))
        await expect(client, "POST", imports_a + "/preview", 413, headers=auth_a,
                     **form_file(b"x" * (2 * 1024 * 1024 + 1), observed=today))
        assert (await expect(client, "GET", imports_a, 200, headers=auth_a)).json() == []
        print("PASS: Bad schema, unknown refs, duplicate rows, oversize, atomic reject")

        await expect(client, "POST", imports_a + "/commit", 409, headers=auth_a,
                     **form_file(csv_data, observed=today, fingerprint="f" * 64))
        imported = (await expect(client, "POST", imports_a + "/commit", 201,
                                 headers=auth_a, **form_file(csv_data, observed=today,
                                                             fingerprint=preview["fingerprint"]))).json()
        assert imported["row_count"] == 2 and imported["snapshot_only"] is True
        await expect(client, "POST", imports_a + "/commit", 409, headers=auth_a,
                     **form_file(csv_data, observed=today, fingerprint=preview["fingerprint"]))
        print("PASS: Preview digest guard, commit, idempotency conflict")

        detail = (await expect(client, "GET", imports_a + "/" + imported["id"], 200,
                               headers=auth_a)).json()
        assert sorted(x["observed_quantity"] for x in detail["rows"]) == [0, 100]
        assert {x["lot_id"] for x in detail["rows"]} == set(lot_ids)
        await expect(client, "GET", imports_a + "/" + imported["id"], 404, headers=auth_b)
        await expect(client, "GET", imports_b + "/" + imported["id"], 404, headers=auth_b)
        assert len((await expect(client, "GET", imports_a, 200, headers=auth_a)).json()) == 1
        print("PASS: Detail, history and cross-organization read isolation")

        # Different physical count on same date is a separate observation, not a stock update.
        other_blob = sample_csv([f"SNAP-SKU,SNAP-SUP,ONE,{expiry.isoformat()},99"])
        other_preview = (await expect(client, "POST", imports_a + "/preview", 200,
                                      headers=auth_a, **form_file(other_blob, observed=today))).json()
        await expect(client, "POST", imports_a + "/commit", 201, headers=auth_a,
                     **form_file(other_blob, observed=today, fingerprint=other_preview["fingerprint"]))
        assert len((await expect(client, "GET", imports_a, 200, headers=auth_a)).json()) == 2
        print("PASS: Historical snapshots remain separate; no live stock overwrite")

        async with AsyncSessionLocal() as db:
            await db.execute(update(OrganizationMembership).where(
                OrganizationMembership.user_id == user_a,
                OrganizationMembership.organization_id == org_a,
            ).values(role="viewer"))
            await db.commit()
        await expect(client, "POST", imports_a + "/preview", 200, headers=auth_a,
                     **form_file(csv_data, observed=today))
        await expect(client, "POST", imports_a + "/commit", 403, headers=auth_a,
                     **form_file(csv_data, observed=today, fingerprint=preview["fingerprint"]))
        print("PASS: Viewer may preview but cannot commit")

        async with AsyncSessionLocal() as db:
            count = await db.scalar(select(text("count(*)")).select_from(InventoryImport).where(
                InventoryImport.organization_id == org_a))
            assert count == 2, count
            assert await db.scalar(select(text("count(*)")).select_from(InventorySnapshotRow)
                                   .join(InventoryImport, InventorySnapshotRow.import_id == InventoryImport.id)
                                   .where(InventoryImport.organization_id == org_a)) == 3
        print("PASS: Exactly two committed imports and three snapshot rows")

    print("PASS: Step 9 CSV imports integration smoke completed")


if __name__ == "__main__":
    asyncio.run(main())
