from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.organizations.dependencies import (
    require_read_membership,
    require_write_membership,
)
from app.features.organizations.membership_model import OrganizationMembership
from app.features.products.repository import get_product, list_products
from app.features.products.schema import ProductCreate, ProductResponse, ProductUpdate
from app.features.products.service import (
    ProductSkuConflict, create_product, update_product
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/products",
    tags=["Products"],
)
ReadMember = Annotated[OrganizationMembership, Depends(require_read_membership)]
WriteMember = Annotated[OrganizationMembership, Depends(require_write_membership)]
Db = Annotated[AsyncSession, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProductResponse)
async def create_route(
    organization_id: UUID, payload: ProductCreate,
    membership: WriteMember, db: Db,
):
    try:
        return await create_product(db, organization_id, payload)
    except ProductSkuConflict:
        raise HTTPException(status_code=409, detail="Product SKU already exists") from None


@router.get("", response_model=list[ProductResponse])
async def list_route(
    organization_id: UUID, membership: ReadMember, db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await list_products(db, organization_id, limit, offset)


@router.get("/{product_id}", response_model=ProductResponse)
async def detail_route(
    organization_id: UUID, product_id: UUID, membership: ReadMember, db: Db,
):
    product = await get_product(db, organization_id, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_route(
    organization_id: UUID, product_id: UUID, payload: ProductUpdate,
    membership: WriteMember, db: Db,
):
    try:
        product = await update_product(db, organization_id, product_id, payload)
    except ProductSkuConflict:
        raise HTTPException(status_code=409, detail="Product SKU already exists") from None
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
