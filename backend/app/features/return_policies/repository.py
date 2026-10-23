"""Every query is scoped by organization. No latest-policy fallback after expiry."""
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.return_policies.model import ReturnPolicyVersion
from app.features.suppliers.model import Supplier


async def lock_supplier(db: AsyncSession, org_id: UUID, supplier_id: UUID) -> Supplier | None:
    # Serializes version assignment for the SAME supplier, across API processes.
    return await db.scalar(
        select(Supplier).where(
            Supplier.organization_id == org_id, Supplier.id == supplier_id,
        ).with_for_update()
    )


async def last_policy(db: AsyncSession, org_id: UUID, supplier_id: UUID) -> ReturnPolicyVersion | None:
    return await db.scalar(
        select(ReturnPolicyVersion).where(
            ReturnPolicyVersion.organization_id == org_id,
            ReturnPolicyVersion.supplier_id == supplier_id,
        ).order_by(ReturnPolicyVersion.version.desc()).limit(1)
    )


async def get_policy(db: AsyncSession, org_id: UUID, policy_id: UUID) -> ReturnPolicyVersion | None:
    return await db.scalar(
        select(ReturnPolicyVersion).where(
            ReturnPolicyVersion.organization_id == org_id,
            ReturnPolicyVersion.id == policy_id,
        )
    )


async def list_policies(
    db: AsyncSession, org_id: UUID, *, supplier_id: UUID | None,
    limit: int, offset: int,
) -> list[ReturnPolicyVersion]:
    q = select(ReturnPolicyVersion).where(ReturnPolicyVersion.organization_id == org_id)
    if supplier_id is not None:
        q = q.where(ReturnPolicyVersion.supplier_id == supplier_id)
    q = q.order_by(
        ReturnPolicyVersion.supplier_id, ReturnPolicyVersion.version.desc(), ReturnPolicyVersion.id,
    ).limit(limit).offset(offset)
    return list((await db.scalars(q)).all())


async def effective_policy(
    db: AsyncSession, org_id: UUID, supplier_id: UUID, as_of: date,
) -> ReturnPolicyVersion | None:
    # Newer effective_from supersedes earlier versions even when earlier effective_to=None.
    # Expired latest version NEVER falls back to a previously superseded version.
    return await db.scalar(
        select(ReturnPolicyVersion).where(
            ReturnPolicyVersion.organization_id == org_id,
            ReturnPolicyVersion.supplier_id == supplier_id,
            ReturnPolicyVersion.effective_from <= as_of,
        ).order_by(
            ReturnPolicyVersion.effective_from.desc(), ReturnPolicyVersion.version.desc(),
        ).limit(1)
    )
