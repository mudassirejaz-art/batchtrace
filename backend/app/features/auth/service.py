from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.features.auth.model import User
from app.features.auth.repository import find_user_by_email
from app.features.auth.schema import RegisterRequest, RegisterResponse
from app.features.organizations.membership_model import OrganizationMembership
from app.features.organizations.model import Organization


class RegistrationConflict(Exception):
    pass


class InvalidCredentials(Exception):
    pass


async def register(db: AsyncSession, data: RegisterRequest) -> RegisterResponse:
    user_id = uuid4()
    organization_id = uuid4()
    user = User(
        id=user_id,
        email=str(data.email),
        password_hash=hash_password(data.password),
    )
    organization = Organization(
        id=organization_id,
        name=data.organization_name,
        slug=data.organization_slug,
    )
    membership = OrganizationMembership(
        id=uuid4(),
        user_id=user_id,
        organization_id=organization_id,
        role="owner",
    )
    try:
        async with db.begin():
            # Insert parent records before membership.
            db.add_all([user, organization])
            await db.flush()

            # Foreign keys now reference existing rows.
            db.add(membership)
            await db.flush()
    except IntegrityError as exc:
        # Only PostgreSQL unique violations are registration conflicts.
        # Do not hide FK or CHECK constraint bugs as HTTP 409.
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise RegistrationConflict from exc
        raise

    return RegisterResponse(
        user_id=user_id,
        organization_id=organization_id,
        organization_slug=data.organization_slug,
    )


async def login(db: AsyncSession, email: str, password: str) -> str:
    user = await find_user_by_email(db, email)
    password_valid = verify_password(
        password, user.password_hash if user else DUMMY_HASH
    )
    if not user or not password_valid or not user.is_active:
        raise InvalidCredentials
    return create_access_token(user.id)
