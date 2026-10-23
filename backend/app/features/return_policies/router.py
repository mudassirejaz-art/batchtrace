"""Supplier policy history and lot-specific date-window assessment."""
from datetime import date, datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.organizations.dependencies import require_read_membership, require_write_membership
from app.features.organizations.membership_model import OrganizationMembership
from app.features.return_policies.repository import get_policy, list_policies
from app.features.return_policies.schema import PolicyCreate, PolicyResponse, ReturnWindowResponse
from app.features.return_policies.service import (
    PolicyConflict, PolicyDateOverflow, UnknownLot, UnknownSupplier,
    create_policy, evaluate_lot,
)

policy_router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/return-policies",
    tags=["Return policies"],
)
evaluation_router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/lots",
    tags=["Return policy evaluations"],
)
ReadMember = Annotated[OrganizationMembership, Depends(require_read_membership)]
WriteMember = Annotated[OrganizationMembership, Depends(require_write_membership)]
Db = Annotated[AsyncSession, Depends(get_db)]


@policy_router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_route(organization_id: UUID, payload: PolicyCreate, membership: WriteMember, db: Db):
    try:
        return await create_policy(db, organization_id, payload)
    except UnknownSupplier:
        raise HTTPException(status_code=404, detail="Supplier not found in organization") from None
    except PolicyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@policy_router.get("", response_model=list[PolicyResponse])
async def list_route(
    organization_id: UUID, membership: ReadMember, db: Db,
    supplier_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await list_policies(
        db, organization_id, supplier_id=supplier_id, limit=limit, offset=offset,
    )


@policy_router.get("/{policy_id}", response_model=PolicyResponse)
async def detail_route(organization_id: UUID, policy_id: UUID, membership: ReadMember, db: Db):
    policy = await get_policy(db, organization_id, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@evaluation_router.get("/{lot_id}/return-window", response_model=ReturnWindowResponse)
async def return_window_route(
    organization_id: UUID, lot_id: UUID, membership: ReadMember, db: Db,
    as_of: date | None = None,
):
    reference = as_of if as_of is not None else datetime.now(timezone.utc).date()
    try:
        return await evaluate_lot(db, organization_id, lot_id, reference)
    except UnknownLot:
        raise HTTPException(status_code=404, detail="Lot not found") from None
    except PolicyDateOverflow:
        raise HTTPException(status_code=422, detail="Date range outside supported calendar") from None
