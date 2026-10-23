"""Org-scoped verification queries; exact latest CSV observation lookup."""
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.model import InventoryImport, InventorySnapshotRow
from app.features.lots.model import Lot
from app.features.verifications.model import StockVerification


async def locked_lot(db: AsyncSession, org_id: UUID, lot_id: UUID):
    # Serializes concurrent submissions for this lot, including different idempotency keys.
    return await db.scalar(
        select(Lot).where(Lot.id == lot_id, Lot.organization_id == org_id).with_for_update()
    )


async def latest_snapshot(db: AsyncSession, org_id: UUID, lot_id: UUID, today: date):
    return (await db.execute(
        select(InventorySnapshotRow, InventoryImport)
        .join(InventoryImport, InventoryImport.id == InventorySnapshotRow.import_id)
        .where(
            InventoryImport.organization_id == org_id,
            InventorySnapshotRow.lot_id == lot_id,
            InventoryImport.observed_on <= today,
        )
        .order_by(
            InventoryImport.observed_on.desc(),
            InventoryImport.created_at.desc(),
            InventoryImport.id.desc(),
            InventorySnapshotRow.id.desc(),
        )
        .limit(1)
    )).first()


async def by_idempotency(db: AsyncSession, org_id: UUID, key: str):
    return await db.scalar(select(StockVerification).where(
        StockVerification.organization_id == org_id,
        StockVerification.idempotency_key == key,
    ))


async def by_id(db: AsyncSession, org_id: UUID, verification_id: UUID, lock: bool = False):
    query = select(StockVerification).where(
        StockVerification.id == verification_id,
        StockVerification.organization_id == org_id,
    )
    if lock:
        query = query.with_for_update()
    return await db.scalar(query)


async def list_by_organization(db: AsyncSession, org_id: UUID, limit: int, offset: int):
    return (await db.scalars(
        select(StockVerification)
        .where(StockVerification.organization_id == org_id)
        .order_by(StockVerification.created_at.desc(), StockVerification.id.desc())
        .limit(limit).offset(offset)
    )).all()
