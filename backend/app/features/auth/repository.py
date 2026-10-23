from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.model import User


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email))


async def find_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)
