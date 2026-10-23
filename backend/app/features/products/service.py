from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.products.model import Product
from app.features.products.repository import get_product
from app.features.products.schema import ProductCreate, ProductUpdate


class ProductSkuConflict(Exception):
    pass


async def _save(db: AsyncSession, product: Product) -> Product:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise ProductSkuConflict from exc
        raise
    return product


async def create_product(
    db: AsyncSession, organization_id: UUID, payload: ProductCreate
) -> Product:
    product = Product(
        organization_id=organization_id, sku=payload.sku, name=payload.name
    )
    db.add(product)
    return await _save(db, product)


async def update_product(
    db: AsyncSession, organization_id: UUID, product_id: UUID,
    payload: ProductUpdate,
) -> Product | None:
    product = await get_product(db, organization_id, product_id)
    if product is None:
        return None
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(product, field, value)
    if changes:
        await _save(db, product)
    return product
