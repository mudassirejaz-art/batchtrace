"""Batch/lot and expiry-watch REST endpoints."""
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.lots.repository import get_lot, list_expiring_lots, list_lots
from app.features.lots.schema import ExpiryWatchItem, LotCreate, LotResponse
from app.features.lots.service import (
    LotAlreadyExists, LotReferenceNotFound, create_lot,
)
from app.features.organizations.dependencies import (
    require_read_membership, require_write_membership,
)
from app.features.organizations.membership_model import OrganizationMembership

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/lots",
    tags=["Lots"],
)
ReadMember = Annotated[OrganizationMembership, Depends(require_read_membership)]
WriteMember = Annotated[OrganizationMembership, Depends(require_write_membership)]
Db = Annotated[AsyncSession, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=LotResponse)
async def create_route(
    organization_id: UUID, payload: LotCreate,
    membership: WriteMember, db: Db,
):
    try:
        return await create_lot(db, organization_id, payload)
    except LotReferenceNotFound:
        raise HTTPException(
            status_code=404, detail="Product or supplier not found in organization"
        ) from None
    except LotAlreadyExists:
        raise HTTPException(status_code=409, detail="Lot already exists") from None


@router.get("", response_model=list[LotResponse])
async def list_route(
    organization_id: UUID, membership: ReadMember, db: Db,
    product_id: UUID | None = None,
    supplier_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await list_lots(
        db, organization_id,
        product_id=product_id, supplier_id=supplier_id,
        limit=limit, offset=offset,
    )


@router.get("/expiry-watch", response_model=list[ExpiryWatchItem])
async def expiry_watch_route(
    organization_id: UUID, membership: ReadMember, db: Db,
    within_days: Annotated[int, Query(ge=0, le=365)] = 30,
    as_of: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    # UTC calendar day is the explicit default. Organization-local calendar
    # settings can be added once organizations have configurable timezones.
    reference_date = as_of or datetime.now(timezone.utc).date()
    try:
        until_date = reference_date + timedelta(days=within_days)
    except OverflowError:
        raise HTTPException(status_code=422, detail="Invalid date range") from None

    rows = await list_expiring_lots(
        db, organization_id,
        from_date=reference_date, until_date=until_date,
        limit=limit, offset=offset,
    )
    return [
        ExpiryWatchItem(
            **LotResponse.model_validate(lot).model_dump(),
            days_until_expiry=(lot.expiry_date - reference_date).days,
            urgency=("due_today" if lot.expiry_date == reference_date else "upcoming"),
        )
        for lot in rows
    ]


@router.get("/{lot_id}", response_model=LotResponse)
async def detail_route(
    organization_id: UUID, lot_id: UUID, membership: ReadMember, db: Db,
):
    lot = await get_lot(db, organization_id, lot_id)
    if lot is None:
        raise HTTPException(status_code=404, detail="Lot not found")
    return lot
