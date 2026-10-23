"""PostgreSQL-backed login throttling with atomic updates across workers.

This is a defense-in-depth fixed-window limit, not a complete DDoS solution.
Only HMAC digests are persisted; raw IP addresses/emails are not stored here.
"""
import hashlib
import hmac
from math import ceil

from fastapi import HTTPException, Request
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

# Login attempts allowed per window, including successful login attempts.
IP_EMAIL_LIMIT, IP_EMAIL_WINDOW_SECONDS = 6, 120
IP_LIMIT, IP_WINDOW_SECONDS = 100, 60

_ATOMIC_COUNTER = text("""
    INSERT INTO auth_login_rate_limits
        (throttle_key, window_start, attempt_count, updated_at)
    VALUES (:key, CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP)
    ON CONFLICT (throttle_key) DO UPDATE SET
        attempt_count = CASE
            WHEN auth_login_rate_limits.window_start
                  <= CURRENT_TIMESTAMP - (:window_seconds * INTERVAL '1 second')
            THEN 1
            ELSE auth_login_rate_limits.attempt_count + 1
        END,
        window_start = CASE
            WHEN auth_login_rate_limits.window_start
                  <= CURRENT_TIMESTAMP - (:window_seconds * INTERVAL '1 second')
            THEN CURRENT_TIMESTAMP
            ELSE auth_login_rate_limits.window_start
        END,
        updated_at = CURRENT_TIMESTAMP
    RETURNING attempt_count,
        EXTRACT(EPOCH FROM (
            window_start + (:window_seconds * INTERVAL '1 second')
            - CURRENT_TIMESTAMP
        )) AS retry_seconds
""")


def _digest(kind: str, value: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        f"{kind}|{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def enforce_login_throttle(request: Request, normalized_email: str) -> None:
    # Use the ASGI client host. Do NOT trust arbitrary X-Forwarded-For headers.
    # Configure trusted proxies explicitly for a future reverse-proxy deployment.
    host = request.client.host if request.client else "unknown"
    subjects = (
        (_digest("ip", host), IP_LIMIT, IP_WINDOW_SECONDS),
        (_digest("ip-email", f"{host}|{normalized_email.casefold()}"),
         IP_EMAIL_LIMIT, IP_EMAIL_WINDOW_SECONDS),
    )
    retry_after = 0

    # Independent transaction: a failed password verification cannot roll back
    # its own rate-limit counter. ON CONFLICT serializes concurrent attempts.
    async with engine.begin() as connection:
        for key, max_attempts, window_seconds in subjects:
            result = await connection.execute(
                _ATOMIC_COUNTER,
                {"key": key, "window_seconds": window_seconds},
            )
            row = result.one()
            if row.attempt_count > max_attempts:
                retry_after = max(
                    retry_after,
                    max(1, ceil(float(row.retry_seconds))),
                )

    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
