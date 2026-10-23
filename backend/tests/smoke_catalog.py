"""Step 6 integration smoke; writes unique test accounts+records to local batchtrace_db.

Use: PYTHONPATH="$PWD" python tests/smoke_catalog.py
No external network calls: ASGITransport calls the in-process FastAPI app.
"""
import asyncio
from uuid import uuid4

import httpx
from sqlalchemy import update

from app.db.session import AsyncSessionLocal, engine
from app.features.organizations.membership_model import OrganizationMembership
from app.main import app


async def register_and_login(client: httpx.AsyncClient, suffix: str):
    email = f"catalog-{suffix}@example.com"
    password = "LocalCatalog_Smoke_2026!"
    r = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "organization_name": f"Catalog smoke {suffix}",
        "organization_slug": f"catalog-smoke-{suffix}",
    })
    assert r.status_code == 201, ("register", r.status_code, r.text)
    org_id = r.json()["organization_id"]
    user_id = r.json()["user_id"]
    r = await client.post("/api/v1/auth/login", json={
        "email": email, "password": password,
    })
    assert r.status_code == 200, ("login", r.status_code, r.text)
    return org_id, user_id, {"Authorization": f"Bearer {r.json()['access_token']}"}


async def expect(client, method, url, expected, **kwargs):
    r = await client.request(method, url, **kwargs)
    assert r.status_code == expected, (method, url, expected, r.status_code, r.text)
    return r


async def main():
    if engine.url.host not in {"127.0.0.1", "localhost", "::1"} or engine.url.database != "batchtrace_db":
        raise SystemExit("STOP: Smoke test requires local batchtrace_db only")
    async with engine.connect() as conn:
        from sqlalchemy import text
        database = await conn.scalar(text("SELECT current_database()"))
        assert database == "batchtrace_db", f"STOP: not local batchtrace_db: {database}"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        unique = uuid4().hex[:12]
        org_a, user_a, auth_a = await register_and_login(client, unique + "a")
        org_b, _, auth_b = await register_and_login(client, unique + "b")
        a_s = f"/api/v1/organizations/{org_a}/suppliers"
        a_p = f"/api/v1/organizations/{org_a}/products"
        b_s = f"/api/v1/organizations/{org_b}/suppliers"
        b_p = f"/api/v1/organizations/{org_b}/products"
        print("PASS: Two isolated organizations created")

        await expect(client, "POST", a_s, 401, json={"code": "S1", "name": "X"})
        await expect(client, "GET", a_p, 401)
        print("PASS: Anonymous access blocked")

        s = await expect(client, "POST", a_s, 201, headers=auth_a,
                         json={"code": " s1 ", "name": " Supplier One "})
        supplier_id = s.json()["id"]
        assert s.json()["code"] == "S1" and s.json()["name"] == "Supplier One"
        p = await expect(client, "POST", a_p, 201, headers=auth_a,
                         json={"sku": " sku-1 ", "name": " Product One "})
        product_id = p.json()["id"]
        assert p.json()["sku"] == "SKU-1" and p.json()["name"] == "Product One"
        print("PASS: Supplier and product created and normalized")

        await expect(client, "POST", a_s, 409, headers=auth_a,
                     json={"code": "s1", "name": "Duplicate"})
        await expect(client, "POST", a_p, 409, headers=auth_a,
                     json={"sku": "sku-1", "name": "Duplicate"})
        print("PASS: Duplicate supplier code and product SKU rejected")

        # The same business codes are allowed in different organizations.
        await expect(client, "POST", b_s, 201, headers=auth_b,
                     json={"code": "S1", "name": "Other org supplier"})
        await expect(client, "POST", b_p, 201, headers=auth_b,
                     json={"sku": "SKU-1", "name": "Other org product"})
        print("PASS: Codes unique per organization, not globally")

        s_list = await expect(client, "GET", a_s, 200, headers=auth_a)
        p_list = await expect(client, "GET", a_p, 200, headers=auth_a)
        assert [x["id"] for x in s_list.json()] == [supplier_id]
        assert [x["id"] for x in p_list.json()] == [product_id]
        await expect(client, "GET", f"{a_s}/{supplier_id}", 200, headers=auth_a)
        await expect(client, "GET", f"{a_p}/{product_id}", 200, headers=auth_a)
        await expect(client, "GET", a_s + "?limit=0", 422, headers=auth_a)
        await expect(client, "GET", a_p + "?limit=101", 422, headers=auth_a)
        print("PASS: List, detail, and pagination validation")

        await expect(client, "PATCH", f"{a_s}/{supplier_id}", 200, headers=auth_a,
                     json={"name": "Supplier Updated"})
        await expect(client, "PATCH", f"{a_p}/{product_id}", 200, headers=auth_a,
                     json={"name": "Product Updated"})
        await expect(client, "PATCH", f"{a_s}/{supplier_id}", 422, headers=auth_a,
                     json={"organization_id": str(org_b)})
        await expect(client, "POST", a_p, 422, headers=auth_a,
                     json={"sku": "SKU-2", "name": "  "})
        print("PASS: Safe updates; protected fields and invalid input rejected")

        for url in (a_s, a_p, f"{a_s}/{supplier_id}", f"{a_p}/{product_id}"):
            await expect(client, "GET", url, 404, headers=auth_b)
        await expect(client, "POST", a_s, 404, headers=auth_b,
                     json={"code": "S3", "name": "No"})
        await expect(client, "PATCH", f"{a_p}/{product_id}", 404, headers=auth_b,
                     json={"name": "No"})
        await expect(client, "GET", f"{b_s}/{supplier_id}", 404, headers=auth_b)
        await expect(client, "GET", f"{b_p}/{product_id}", 404, headers=auth_b)
        await expect(client, "GET", b_s, 200, headers=auth_b)
        await expect(client, "GET", b_p, 200, headers=auth_b)
        print("PASS: Cross-organization reads and writes blocked")

        # Change only the uniquely created test membership, then verify viewer rights.
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(OrganizationMembership)
                .where(OrganizationMembership.organization_id == org_a)
                .where(OrganizationMembership.user_id == user_a)
                .values(role="viewer")
            )
            await db.commit()
        await expect(client, "GET", a_s, 200, headers=auth_a)
        await expect(client, "GET", a_p, 200, headers=auth_a)
        await expect(client, "POST", a_s, 403, headers=auth_a,
                     json={"code": "S4", "name": "Denied"})
        await expect(client, "POST", a_p, 403, headers=auth_a,
                     json={"sku": "SKU4", "name": "Denied"})
        await expect(client, "PATCH", f"{a_s}/{supplier_id}", 403, headers=auth_a,
                     json={"name": "Denied"})
        print("PASS: Viewer can read but cannot create/update")

    await engine.dispose()
    print("PASS: Step 6 catalog smoke completed")


if __name__ == "__main__":
    asyncio.run(main())
