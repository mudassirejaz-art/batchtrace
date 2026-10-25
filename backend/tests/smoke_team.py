"""Step 22 local-only organization membership and independent review integration smoke.
Creates uniquely named local test accounts and related records; no existing-data cleanup.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from sqlalchemy import text

from app.db.session import engine
from app.main import app


async def expect(client, method, path, expected, **kwargs):
    response = await client.request(method, path, **kwargs)
    assert response.status_code == expected, (method, path, expected, response.status_code, response.text)
    return response


async def register(client, suffix):
    email = f"team22-{suffix}@example.com"
    password = "BatchTraceTeamTest2026!"
    record = await expect(client, "POST", "/api/v1/auth/register", 201, json={
        "email": email, "password": password, "organization_name": f"Team {suffix}",
        "organization_slug": f"team22-{suffix}",
    })
    token = await expect(client, "POST", "/api/v1/auth/login", 200,
                         json={"email": email, "password": password})
    return email, record.json(), {"Authorization": "Bearer " + token.json()["access_token"]}


async def main():
    if engine.url.host not in {"localhost", "127.0.0.1", "::1"} or engine.url.database != "batchtrace_db" or engine.url.username != "batchtrace_dev":
        raise SystemExit("STOP: Team smoke only allowed on local batchtrace_db with batchtrace_dev")
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT current_database()")) == "batchtrace_db"
        revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision == "e7b54d260a91", ("Unexpected migration revision", revision)
    print("PASS: Local database and Step 15 revision guarded")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        suffix = uuid4().hex[:12]
        email_a, a, auth_a = await register(client, suffix + "a")
        email_b, b, auth_b = await register(client, suffix + "b")
        email_c, c, auth_c = await register(client, suffix + "c")
        base = f"/api/v1/organizations/{a['organization_id']}"
        team = base + "/team"
        assert len((await expect(client, "GET", team, 200, headers=auth_a)).json()) == 1
        await expect(client, "GET", team, 401)
        await expect(client, "GET", team, 404, headers=auth_b)
        await expect(client, "POST", team, 404, headers=auth_b, json={"email":email_c,"role":"staff"})
        print("PASS: Anonymous and foreign organization access blocked")

        await expect(client, "POST", team, 422, headers=auth_a, json={"email":email_b,"role":"owner"})
        await expect(client, "POST", team, 404, headers=auth_a, json={"email":"not-a-user-22@example.com","role":"staff"})
        invited = (await expect(client, "POST", team, 201, headers=auth_a,
                                json={"email":email_b.upper(),"role":"admin"})).json()
        assert invited["role"] == "admin" and invited["user_id"] == b["user_id"]
        await expect(client, "POST", team, 409, headers=auth_a, json={"email":email_b,"role":"admin"})
        listing = (await expect(client, "GET", team, 200, headers=auth_b)).json()
        assert len(listing) == 2 and {x["email"] for x in listing} == {email_a,email_b}
        organizations = (await expect(client, "GET", "/api/v1/organizations/me", 200, headers=auth_b)).json()
        assert a["organization_id"] in [str(x["id"]) for x in organizations]
        print("PASS: Existing registered user added; workspace visible; duplicate prevented")

        viewer = (await expect(client, "POST", team, 201, headers=auth_b,
                               json={"email":email_c,"role":"viewer"})).json()
        await expect(client, "POST", team, 403, headers=auth_b, json={"email":email_c,"role":"admin"})
        await expect(client, "POST", team, 403, headers=auth_c, json={"email":email_a,"role":"staff"})
        await expect(client, "PATCH", team+"/"+invited["membership_id"], 403,
                     headers=auth_b, json={"role":"staff"})
        await expect(client, "GET", team, 403, headers=auth_c)
        await expect(client, "PATCH", team+"/"+viewer["membership_id"], 403, headers=auth_c, json={"role":"staff"})
        print("PASS: Viewer read only; admin cannot promote admin; no self role edits")

        # Real independent reviewer API test, not just a frontend preview.
        now = datetime.now(timezone.utc).date()
        expiry = now + timedelta(days=12)
        supplier = (await expect(client, "POST", base+"/suppliers", 201, headers=auth_a,
                         json={"code":"TEAM22-SUP", "name":"Team verification supplier"})).json()["id"]
        product = (await expect(client, "POST", base+"/products", 201, headers=auth_a,
                         json={"sku":"TEAM22-SKU", "name":"Team verification product"})).json()["id"]
        await expect(client, "POST", base+"/return-policies", 201, headers=auth_a,
                     json={"supplier_id":supplier,"days_before_expiry":45,"days_after_expiry":15,
                           "effective_from":(now-timedelta(days=3)).isoformat()})
        lot = (await expect(client, "POST", base+"/lots", 201, headers=auth_a,
                        json={"product_id":product,"supplier_id":supplier,"batch_number":"TEAM22-BATCH",
                              "expiry_date":expiry.isoformat()})).json()["id"]
        csv=("product_sku,supplier_code,batch_number,expiry_date,quantity\n"
             f"TEAM22-SKU,TEAM22-SUP,TEAM22-BATCH,{expiry.isoformat()},20\n").encode()
        upload={"file":("team22.csv",csv,"text/csv")}
        data={"observed_on":now.isoformat()}
        preview=(await expect(client,"POST",base+"/imports/preview",200,headers=auth_a,data=data,files=upload)).json()
        assert preview["valid"],preview
        imported=(await expect(client,"POST",base+"/imports/commit",201,headers=auth_a,
                               data={**data,"preview_fingerprint":preview["fingerprint"]},files=upload)).json()
        verify=base+"/recovery/verifications"
        request={"lot_id":lot,"import_id":imported["id"],"counted_quantity":20,
                 "note":"Twenty units counted in local integration test."}
        created=(await expect(client,"POST",verify,201,headers={**auth_a,"Idempotency-Key":"team22-"+suffix},json=request)).json()
        await expect(client,"POST",verify+"/"+created["id"]+"/review",403,headers=auth_a,
                     json={"decision":"approved","reason":"Checked these twenty units independently."})
        await expect(client,"POST",verify+"/"+created["id"]+"/review",403,headers=auth_c,
                     json={"decision":"approved","reason":"I have reviewed the warehouse record."})
        result=(await expect(client,"POST",verify+"/"+created["id"]+"/review",200,headers=auth_b,
                     json={"decision":"approved","reason":"Independently checked the warehouse count."})).json()
        assert result["verification"]["status"]=="approved"
        print("PASS: Second organization member approves first user's verification; self/viewer blocked")

        # Owner may change or remove non-owner users; keep owner and historical review intact.
        revised=(await expect(client,"PATCH",team+"/"+viewer["membership_id"],200,headers=auth_a,
                       json={"role":"staff"})).json()
        assert revised["role"]=="staff"
        owner_member=next(x for x in (await expect(client,"GET",team,200,headers=auth_a)).json() if x["role"]=="owner")
        await expect(client,"DELETE",team+"/"+owner_member["membership_id"],403,headers=auth_a)
        await expect(client,"DELETE",team+"/"+viewer["membership_id"],204,headers=auth_a)
        await expect(client,"GET",team,404,headers=auth_c)
        remaining=(await expect(client,"GET",team,200,headers=auth_a)).json()
        assert len(remaining)==2
        print("PASS: Role update, remove member, last owner protection; historical review retained")

    print("PASS: Step 22 team + independent reviewer integration smoke completed")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
