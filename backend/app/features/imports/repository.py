"""Organization-scoped read paths for imported snapshots."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.model import InventoryImport, InventorySnapshotRow


async def get_import(db: AsyncSession, organization_id: UUID, import_id: UUID):
    return await db.scalar(
        select(InventoryImport).where(
            InventoryImport.organization_id == organization_id,
            InventoryImport.id == import_id,
        )
    )


async def list_imports(db: AsyncSession, organization_id: UUID, limit: int, offset: int):
    result = await db.scalars(
        select(InventoryImport)
        .where(InventoryImport.organization_id == organization_id)
        .order_by(InventoryImport.created_at.desc(), InventoryImport.id.desc())
        .limit(limit).offset(offset)
    )
    return list(result.all())


async def list_import_rows(db: AsyncSession, import_id: UUID):
    result = await db.scalars(
        select(InventorySnapshotRow)
        .where(InventorySnapshotRow.import_id == import_id)
        .order_by(InventorySnapshotRow.lot_id)
    )
    return list(result.all())
