"""Organization-scoped database queries; never query a lot by id alone."""
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lots.model import Lot


async def get_lot(
    db: AsyncSession, organization_id: UUID, lot_id: UUID,
) -> Lot | None:
    return await db.scalar(
        select(Lot).where(Lot.id == lot_id, Lot.organization_id == organization_id)
    )


async def list_lots(
    db: AsyncSession, organization_id: UUID,
    *, product_id: UUID | None, supplier_id: UUID | None,
    limit: int, offset: int,
) -> list[Lot]:
    query = select(Lot).where(Lot.organization_id == organization_id)
    if product_id is not None:
        query = query.where(Lot.product_id == product_id)
    if supplier_id is not None:
        query = query.where(Lot.supplier_id == supplier_id)
    query = query.order_by(Lot.expiry_date, Lot.id).limit(limit).offset(offset)
    return list((await db.scalars(query)).all())


async def list_expiring_lots(
    db: AsyncSession, organization_id: UUID,
    *, from_date: date, until_date: date,
    limit: int, offset: int,
) -> list[Lot]:
    query = (
        select(Lot)
        .where(
            Lot.organization_id == organization_id,
            Lot.expiry_date >= from_date,
            Lot.expiry_date <= until_date,
        )
        .order_by(Lot.expiry_date, Lot.id)
        .limit(limit)
        .offset(offset)
    )
    return list((await db.scalars(query)).all())
