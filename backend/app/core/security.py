from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings

_password_hasher = PasswordHash.recommended()
DUMMY_HASH = _password_hasher.hash("not-a-real-account-password")
ALGORITHM = "HS256"
ISSUER = "batchtrace"
AUDIENCE = "batchtrace-api"


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return _password_hasher.verify(password, hashed_password)


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "jti": str(uuid4()),
        "token_type": "access",
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> UUID:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": [
                "sub", "iss", "aud", "iat", "nbf", "exp", "jti", "token_type"
            ]},
        )
        if claims.get("token_type") != "access":
            raise ValueError("Incorrect token type")
        return UUID(claims["sub"])
    except (InvalidTokenError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("Invalid or expired token") from exc
