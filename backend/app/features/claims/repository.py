"""Organization-filtered claim queries and serialized verification allocation."""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.claims.model import ClaimEvent, ReturnClaim
from app.features.verifications.model import StockVerification


async def locked_verification(db: AsyncSession, organization_id: UUID, verification_id: UUID):
    return await db.scalar(
        select(StockVerification).where(
            StockVerification.organization_id == organization_id,
            StockVerification.id == verification_id,
        ).with_for_update()
    )


async def claim_by_key(db: AsyncSession, organization_id: UUID, key: str):
    return await db.scalar(select(ReturnClaim).where(
        ReturnClaim.organization_id == organization_id,
        ReturnClaim.idempotency_key == key,
    ))


async def claim_by_id(db: AsyncSession, organization_id: UUID, claim_id: UUID, *, lock: bool = False):
    query = select(ReturnClaim).where(
        ReturnClaim.organization_id == organization_id, ReturnClaim.id == claim_id,
    )
    return await db.scalar(query.with_for_update() if lock else query)


async def allocated_quantity(db: AsyncSession, verification_id: UUID) -> int:
    # Conservative policy: all claims retain their allocations, including rejected claims.
    return int(await db.scalar(select(func.coalesce(func.sum(ReturnClaim.quantity), 0)).where(
        ReturnClaim.verification_id == verification_id,
    )) or 0)


async def list_claims(db: AsyncSession, organization_id: UUID, limit: int, offset: int):
    return (await db.scalars(select(ReturnClaim).where(
        ReturnClaim.organization_id == organization_id,
    ).order_by(ReturnClaim.created_at.desc(), ReturnClaim.id.desc()).limit(limit).offset(offset))).all()


async def list_events(db: AsyncSession, claim_id: UUID):
    return (await db.scalars(select(ClaimEvent).where(
        ClaimEvent.claim_id == claim_id,
    ).order_by(ClaimEvent.created_at, ClaimEvent.id))).all()
