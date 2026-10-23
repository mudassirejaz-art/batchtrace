from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.suppliers.model import Supplier


async def get_supplier(
    db: AsyncSession, organization_id: UUID, supplier_id: UUID
) -> Supplier | None:
    return await db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.organization_id == organization_id,
        )
    )


async def list_suppliers(
    db: AsyncSession, organization_id: UUID, limit: int, offset: int
) -> list[Supplier]:
    result = await db.scalars(
        select(Supplier)
        .where(Supplier.organization_id == organization_id)
        .order_by(Supplier.created_at, Supplier.id)
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())
