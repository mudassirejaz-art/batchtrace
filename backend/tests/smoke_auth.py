"""Integration smoke: creates one randomly named account in local batchtrace_db.

No third-party network APIs or external services are used.
"""
import asyncio
from uuid import uuid4

import httpx

from app.main import app


async def main() -> None:
    unique = uuid4().hex[:12]
    email = f"smoke-{unique}@example.com"
    password = "LocalTest_Only_2026!"
    slug = f"batchtrace-smoke-{unique}"
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        register = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "organization_name": "BatchTrace Smoke Test",
                "organization_slug": slug,
            },
        )
        assert register.status_code == 201, register.text
        assert register.json()["organization_slug"] == slug
        print("PASS: Register and membership created atomically")

        duplicate = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "organization_name": "Duplicate Org",
                "organization_slug": f"duplicate-{unique}",
            },
        )
        assert duplicate.status_code == 409, duplicate.text
        print("PASS: Duplicate registration rejected")

        invalid = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "bad"}
        )
        assert invalid.status_code == 401, invalid.text
        print("PASS: Wrong password rejected")

        login = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        assert login.json()["token_type"] == "bearer"
        print("PASS: Login issues a JWT")

        unauthenticated = await client.get("/api/v1/auth/me")
        assert unauthenticated.status_code == 401, unauthenticated.text
        print("PASS: Protected endpoint blocks anonymous access")

        invalid_token = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}
        )
        assert invalid_token.status_code == 401, invalid_token.text
        print("PASS: Invalid JWT rejected")

        auth = {"Authorization": f"Bearer {token}"}
        me = await client.get("/api/v1/auth/me", headers=auth)
        assert me.status_code == 200, me.text
        assert me.json()["email"] == email
        assert "password_hash" not in me.json()
        print("PASS: Authenticated profile does not leak password hash")

        orgs = await client.get("/api/v1/organizations/me", headers=auth)
        assert orgs.status_code == 200, orgs.text
        assert len(orgs.json()) == 1
        assert orgs.json()[0]["slug"] == slug
        assert orgs.json()[0]["role"] == "owner"
        print("PASS: Organization owner membership verified")

    print("PASS: Step 5 authentication smoke completed")


if __name__ == "__main__":
    asyncio.run(main())
