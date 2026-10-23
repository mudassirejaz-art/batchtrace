"""JWT organization-scoped internal return claims and staff-recorded supplier outcomes."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.claims.repository import claim_by_id, list_claims, list_events
from app.features.claims.schema import (
    ClaimCreate, ClaimNote, ClaimResponse, ClaimDetailResponse, SupplierResponseCreate,
    ClaimEventResponse,
)
from app.features.claims.service import ClaimConflict, ClaimForbidden, ClaimNotFound, create_claim, advance_claim
from app.features.organizations.dependencies import require_read_membership, require_write_membership
from app.features.organizations.membership_model import OrganizationMembership

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/recovery/claims",
    tags=["Supplier return claims (internal workflow)"],
)
Reader = Annotated[OrganizationMembership, Depends(require_read_membership)]
Writer = Annotated[OrganizationMembership, Depends(require_write_membership)]
Db = Annotated[AsyncSession, Depends(get_db)]


def _failure(error: Exception):
    if isinstance(error, ClaimNotFound):
        raise HTTPException(status_code=404, detail="Claim or verification not found") from None
    if isinstance(error, ClaimForbidden):
        raise HTTPException(status_code=403, detail=str(error)) from None
    if isinstance(error, ClaimConflict):
        raise HTTPException(status_code=409, detail=str(error)) from None
    raise error


@router.post("", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    organization_id: UUID, payload: ClaimCreate, membership: Writer, db: Db,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=80,
                                           pattern=r"^[A-Za-z0-9._-]+$")],
):
    try:
        return await create_claim(db, organization_id, membership.user_id, payload, idempotency_key)
    except (ClaimNotFound, ClaimConflict, ClaimForbidden) as exc:
        _failure(exc)


@router.get("", response_model=list[ClaimResponse])
async def list_route(organization_id: UUID, membership: Reader, db: Db,
                     limit: Annotated[int, Query(ge=1, le=100)] = 50,
                     offset: Annotated[int, Query(ge=0)] = 0):
    return await list_claims(db, organization_id, limit, offset)


@router.get("/{claim_id}", response_model=ClaimDetailResponse)
async def detail_route(organization_id: UUID, claim_id: UUID, membership: Reader, db: Db):
    record = await claim_by_id(db, organization_id, claim_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    events = await list_events(db, record.id)
    return ClaimDetailResponse(**ClaimResponse.model_validate(record).model_dump(),
                               events=[ClaimEventResponse.model_validate(e) for e in events])


@router.post("/{claim_id}/approve", response_model=ClaimResponse)
async def approve_route(organization_id: UUID, claim_id: UUID, payload: ClaimNote,
                        membership: Writer, db: Db):
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owner/admin can approve claims")
    try:
        return await advance_claim(db, organization_id, membership.user_id, claim_id, "approve", payload.note)
    except (ClaimNotFound, ClaimConflict, ClaimForbidden) as exc:
        _failure(exc)


@router.post("/{claim_id}/dispatch", response_model=ClaimResponse)
async def dispatch_route(organization_id: UUID, claim_id: UUID, payload: ClaimNote,
                         membership: Writer, db: Db):
    try:
        return await advance_claim(db, organization_id, membership.user_id, claim_id, "dispatch", payload.note)
    except (ClaimNotFound, ClaimConflict, ClaimForbidden) as exc:
        _failure(exc)


@router.post("/{claim_id}/supplier-response", response_model=ClaimResponse)
async def response_route(organization_id: UUID, claim_id: UUID, payload: SupplierResponseCreate,
                         membership: Writer, db: Db):
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owner/admin can record supplier outcomes")
    try:
        return await advance_claim(db, organization_id, membership.user_id, claim_id, "supplier_response",
                                   payload.note, accepted=payload.accepted_quantity,
                                   rejected=payload.rejected_quantity)
    except (ClaimNotFound, ClaimConflict, ClaimForbidden) as exc:
        _failure(exc)
