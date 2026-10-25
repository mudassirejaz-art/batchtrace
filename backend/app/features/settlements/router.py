"""Organization-scoped staff-recorded credit reconciliation; zero external APIs."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.organizations.dependencies import require_finance_membership
from app.features.organizations.membership_model import OrganizationMembership
from app.features.settlements import service
from app.features.settlements.schema import (
    CreditReceiptCreate, CreditReceiptResponse, CreditSummaryResponse,
    CreditTermsCreate, CreditTermsResponse, ReceiptReviewCreate,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/recovery/claims/{claim_id}",
    tags=["Credit settlement (internal evidence only)"],
)
Reader = Annotated[OrganizationMembership, Depends(require_finance_membership)]
Writer = Annotated[OrganizationMembership, Depends(require_finance_membership)]
Db = Annotated[AsyncSession, Depends(get_db)]


def failure(exc: Exception):
    if isinstance(exc, service.SettlementMissing):
        raise HTTPException(status_code=404, detail="Claim or credit resource not found") from None
    if isinstance(exc, service.SettlementConflict):
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if isinstance(exc, service.SettlementForbidden):
        raise HTTPException(status_code=403, detail=str(exc)) from None
    raise exc


@router.post("/credit-terms", response_model=CreditTermsResponse, status_code=status.HTTP_201_CREATED)
async def create_terms(organization_id: UUID, claim_id: UUID, payload: CreditTermsCreate,
                       membership: Writer, db: Db):
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owner/admin may record financial terms")
    try:
        return await service.create_credit_terms(db, organization_id, membership.user_id, claim_id, payload)
    except (service.SettlementMissing, service.SettlementConflict, service.SettlementForbidden) as exc:
        failure(exc)


@router.get("/credit-summary", response_model=CreditSummaryResponse)
async def summary(organization_id: UUID, claim_id: UUID, membership: Reader, db: Db):
    try:
        return await service.credit_summary(db, organization_id, claim_id)
    except (service.SettlementMissing, service.SettlementConflict) as exc:
        failure(exc)


@router.post("/credit-receipts", response_model=CreditReceiptResponse, status_code=status.HTTP_201_CREATED)
async def submit_receipt(
    organization_id: UUID, claim_id: UUID, payload: CreditReceiptCreate,
    membership: Writer, db: Db,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=80,
                                           pattern=r"^[A-Za-z0-9._-]+$")],
):
    try:
        return await service.add_credit_receipt(
            db, organization_id, membership.user_id, claim_id, payload, idempotency_key,
        )
    except (service.SettlementMissing, service.SettlementConflict, service.SettlementForbidden) as exc:
        failure(exc)


@router.get("/credit-receipts", response_model=list[CreditReceiptResponse])
async def list_receipts(organization_id: UUID, claim_id: UUID, membership: Reader, db: Db,
                        limit: Annotated[int, Query(ge=1, le=100)] = 50,
                        offset: Annotated[int, Query(ge=0)] = 0):
    try:
        return await service.list_credit_receipts(db, organization_id, claim_id, limit, offset)
    except (service.SettlementMissing, service.SettlementConflict) as exc:
        failure(exc)


@router.post("/credit-receipts/{receipt_id}/review", response_model=CreditReceiptResponse)
async def review_receipt(organization_id: UUID, claim_id: UUID, receipt_id: UUID,
                         payload: ReceiptReviewCreate, membership: Writer, db: Db):
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owner/admin may review financial evidence")
    try:
        return await service.review_credit_receipt(
            db, organization_id, membership.user_id, claim_id, receipt_id, payload,
        )
    except (service.SettlementMissing, service.SettlementConflict, service.SettlementForbidden) as exc:
        failure(exc)
