"""Tenant-scoped claim lookup; all financial changes serialize on the credit terms row."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.claims.model import ReturnClaim
from app.features.settlements.model import ClaimCreditTerms, CreditReceipt


async def scoped_claim(db: AsyncSession, org_id: UUID, claim_id: UUID, lock: bool = False):
    stmt = select(ReturnClaim).where(
        ReturnClaim.id == claim_id, ReturnClaim.organization_id == org_id,
    )
    return await db.scalar(stmt.with_for_update() if lock else stmt)


async def terms_for_claim(db: AsyncSession, claim_id: UUID, lock: bool = False):
    stmt = select(ClaimCreditTerms).where(ClaimCreditTerms.claim_id == claim_id)
    return await db.scalar(stmt.with_for_update() if lock else stmt)


async def receipts_for_terms(db: AsyncSession, terms_id: UUID):
    return (await db.scalars(select(CreditReceipt).where(
        CreditReceipt.terms_id == terms_id,
    ).order_by(CreditReceipt.created_at, CreditReceipt.id))).all()
