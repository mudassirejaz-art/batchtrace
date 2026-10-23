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
from app.features.suppliers.repository import get_supplier, list_suppliers
from app.features.suppliers.schema import SupplierCreate, SupplierResponse, SupplierUpdate
from app.features.suppliers.service import (
    SupplierCodeConflict, create_supplier, update_supplier
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/suppliers",
    tags=["Suppliers"],
)
ReadMember = Annotated[OrganizationMembership, Depends(require_read_membership)]
WriteMember = Annotated[OrganizationMembership, Depends(require_write_membership)]
Db = Annotated[AsyncSession, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SupplierResponse)
async def create_route(
    organization_id: UUID, payload: SupplierCreate,
    membership: WriteMember, db: Db,
):
    try:
        return await create_supplier(db, organization_id, payload)
    except SupplierCodeConflict:
        raise HTTPException(status_code=409, detail="Supplier code already exists") from None


@router.get("", response_model=list[SupplierResponse])
async def list_route(
    organization_id: UUID, membership: ReadMember, db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await list_suppliers(db, organization_id, limit, offset)


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def detail_route(
    organization_id: UUID, supplier_id: UUID, membership: ReadMember, db: Db,
):
    supplier = await get_supplier(db, organization_id, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.patch("/{supplier_id}", response_model=SupplierResponse)
async def update_route(
    organization_id: UUID, supplier_id: UUID, payload: SupplierUpdate,
    membership: WriteMember, db: Db,
):
    try:
        supplier = await update_supplier(db, organization_id, supplier_id, payload)
    except SupplierCodeConflict:
        raise HTTPException(status_code=409, detail="Supplier code already exists") from None
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier
