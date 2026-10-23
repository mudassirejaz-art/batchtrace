"""Organization-scoped, read-only recovery opportunities."""
from datetime import date, datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.organizations.dependencies import require_read_membership
from app.features.organizations.membership_model import OrganizationMembership
from app.features.recovery.schema import OpportunityResponse
from app.features.recovery.service import EvaluationDateOverflow, list_opportunities

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/recovery",
    tags=["Recovery opportunities (advisory)"],
)
ReadMember = Annotated[OrganizationMembership, Depends(require_read_membership)]
Db = Annotated[AsyncSession, Depends(get_db)]


@router.get("/opportunities", response_model=list[OpportunityResponse])
async def opportunity_list_route(
    organization_id: UUID,
    membership: ReadMember,
    db: Db,
    as_of: date | None = None,
    max_snapshot_age_days: Annotated[int, Query(ge=0, le=3650)] = 7,
    product_id: UUID | None = None,
    supplier_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    reference = as_of if as_of is not None else datetime.now(timezone.utc).date()
    try:
        return await list_opportunities(
            db, organization_id, as_of=reference,
            max_snapshot_age_days=max_snapshot_age_days,
            product_id=product_id, supplier_id=supplier_id,
            limit=limit, offset=offset,
        )
    except EvaluationDateOverflow:
        raise HTTPException(status_code=422, detail="Date range outside supported calendar") from None
