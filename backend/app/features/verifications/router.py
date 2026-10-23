"""Organization-scoped physical verification and independent review."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.organizations.dependencies import require_read_membership, require_write_membership
from app.features.organizations.membership_model import OrganizationMembership
from app.features.verifications.repository import by_id, list_by_organization
from app.features.verifications.schema import (
    DecisionResponse, VerificationCreate, VerificationResponse, VerificationReview,
)
from app.features.verifications.service import (
    ReviewForbidden, VerificationConflict, VerificationNotFound,
    review_verification, submit_verification,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/recovery/verifications",
    tags=["Physical stock verification"],
)
Reader = Annotated[OrganizationMembership, Depends(require_read_membership)]
Writer = Annotated[OrganizationMembership, Depends(require_write_membership)]
Db = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED)
async def submit_route(
    organization_id: UUID, payload: VerificationCreate, membership: Writer, db: Db,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=80,
                                           pattern=r"^[A-Za-z0-9._-]+$")],
):
    try:
        return await submit_verification(db, organization_id, membership.user_id,
                                         payload, idempotency_key)
    except VerificationNotFound:
        raise HTTPException(status_code=404, detail="Lot not found") from None
    except VerificationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.get("", response_model=list[VerificationResponse])
async def list_route(
    organization_id: UUID, membership: Reader, db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await list_by_organization(db, organization_id, limit, offset)


@router.get("/{verification_id}", response_model=VerificationResponse)
async def detail_route(organization_id: UUID, verification_id: UUID, membership: Reader, db: Db):
    record = await by_id(db, organization_id, verification_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Verification not found")
    return record


@router.post("/{verification_id}/review", response_model=DecisionResponse, status_code=200)
async def review_route(
    organization_id: UUID, verification_id: UUID, payload: VerificationReview,
    membership: Writer, db: Db,
):
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owner or admin may review")
    try:
        record, decision = await review_verification(
            db, organization_id, membership.user_id, verification_id, payload,
        )
    except VerificationNotFound:
        raise HTTPException(status_code=404, detail="Verification not found") from None
    except ReviewForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except VerificationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return DecisionResponse(
        verification=VerificationResponse.model_validate(record),
        decision_id=decision.id, reviewed_by_user_id=decision.reviewer_user_id,
        decision=decision.decision, reason=decision.reason, reviewed_at=decision.created_at,
    )
