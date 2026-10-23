from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.suppliers.model import Supplier
from app.features.suppliers.repository import get_supplier
from app.features.suppliers.schema import SupplierCreate, SupplierUpdate


class SupplierCodeConflict(Exception):
    pass


async def _save(db: AsyncSession, supplier: Supplier) -> Supplier:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise SupplierCodeConflict from exc
        raise
    return supplier


async def create_supplier(
    db: AsyncSession, organization_id: UUID, payload: SupplierCreate
) -> Supplier:
    supplier = Supplier(
        organization_id=organization_id, code=payload.code, name=payload.name
    )
    db.add(supplier)
    return await _save(db, supplier)


async def update_supplier(
    db: AsyncSession, organization_id: UUID, supplier_id: UUID,
    payload: SupplierUpdate,
) -> Supplier | None:
    supplier = await get_supplier(db, organization_id, supplier_id)
    if supplier is None:
        return None
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(supplier, field, value)
    if changes:
        await _save(db, supplier)
    return supplier
