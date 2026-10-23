from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.products.model import Product


async def get_product(
    db: AsyncSession, organization_id: UUID, product_id: UUID
) -> Product | None:
    return await db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.organization_id == organization_id,
        )
    )


async def list_products(
    db: AsyncSession, organization_id: UUID, limit: int, offset: int
) -> list[Product]:
    result = await db.scalars(
        select(Product)
        .where(Product.organization_id == organization_id)
        .order_by(Product.created_at, Product.id)
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())
