"""Test login throttling. Creates ONLY rate counters in local batchtrace_db."""
import asyncio
from uuid import uuid4

import httpx
from sqlalchemy import text

from app.db.session import engine
from app.main import app
from app.features.auth.throttle import IP_EMAIL_LIMIT


async def main() -> None:
    if not (
        engine.url.host in {"127.0.0.1", "localhost", "::1"}
        and engine.url.username == "batchtrace_dev"
        and engine.url.database == "batchtrace_db"
    ):
        raise SystemExit("STOP: Not running against local batchtrace_db")
    async with engine.connect() as conn:
        rev = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        assert rev == "e7b54d260a91", rev
    print("PASS: Local DB and login throttle migration guard")

    email = f"throttle-test-{uuid4().hex[:16]}@example.com"
    second_email = f"independent-{uuid4().hex[:16]}@example.com"
    transport = httpx.ASGITransport(app=app, client=("198.51.100.177", 45800))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for i in range(IP_EMAIL_LIMIT):
            r = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": "invalid"}
            )
            assert r.status_code == 401, (i, r.status_code, r.text)
        print("PASS: Initial invalid attempts yield 401")

        limited = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "invalid"}
        )
        assert limited.status_code == 429, limited.text
        assert int(limited.headers["Retry-After"]) >= 1
        print("PASS: Exceeded account/IP window yields 429 and Retry-After")

        other = await client.post(
            "/api/v1/auth/login",
            json={"email": second_email, "password": "invalid"},
        )
        assert other.status_code == 401, other.text
        print("PASS: Unrelated email is not blocked by first email/IP bucket")

        concurrent_email = f"concurrent-{uuid4().hex[:16]}@example.com"
        async def attempt():
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": concurrent_email, "password": "invalid"},
            )
            return response.status_code

        statuses = await asyncio.gather(*[attempt() for _ in range(IP_EMAIL_LIMIT + 4)])
        assert statuses.count(401) == IP_EMAIL_LIMIT, statuses
        assert statuses.count(429) == 4, statuses
        print("PASS: Concurrent requests enforce the same limit atomically")

    await engine.dispose()
    print("PASS: Step 15 login throttle smoke completed")


if __name__ == "__main__":
    asyncio.run(main())
