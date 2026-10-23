"""Lot workflow and domain integrity checks."""
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lots.model import Lot
from app.features.lots.schema import LotCreate
from app.features.products.repository import get_product
from app.features.suppliers.repository import get_supplier


class LotReferenceNotFound(Exception):
    """Product or supplier not accessible under requested organization."""


class LotAlreadyExists(Exception):
    """Same org/product/supplier/batch/expiry was already registered."""


async def create_lot(
    db: AsyncSession, organization_id: UUID, payload: LotCreate,
) -> Lot:
    product = await get_product(db, organization_id, payload.product_id)
    supplier = await get_supplier(db, organization_id, payload.supplier_id)
    if product is None or supplier is None:
        # Do not reveal whether an ID exists in another organization.
        raise LotReferenceNotFound

    lot = Lot(
        organization_id=organization_id,
        product_id=payload.product_id,
        supplier_id=payload.supplier_id,
        batch_number=payload.batch_number,
        expiry_date=payload.expiry_date,
    )
    db.add(lot)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise LotAlreadyExists from exc
        # FK/CHECK/etc. must remain visible as implementation errors.
        raise
    await db.refresh(lot)
    return lot
