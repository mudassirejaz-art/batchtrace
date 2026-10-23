"""Advisory-only opportunity contract. Quantity is unverified CSV observation."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


WindowStatus = Literal[
    "no_policy", "policy_expired", "not_yet_open", "window_open", "window_closed"
]
OpportunityStatus = Literal[
    "verify_stock", "stale_snapshot", "zero_observed", "no_policy",
    "policy_expired", "not_yet_open", "window_closed",
]


class OpportunityResponse(BaseModel):
    organization_id: UUID
    lot_id: UUID
    product_id: UUID
    supplier_id: UUID
    product_sku: str
    supplier_code: str
    batch_number: str
    expiry_date: date

    import_id: UUID
    imported_at: datetime
    observed_on: date
    observed_quantity: int = Field(ge=0)
    snapshot_age_days: int = Field(ge=0)
    snapshot_is_stale: bool

    as_of: date
    policy_id: UUID | None = None
    policy_version: int | None = None
    return_opens_on: date | None = None
    return_closes_on: date | None = None
    date_window_status: WindowStatus
    opportunity_status: OpportunityStatus

    requires_physical_verification: Literal[True] = True
    authoritative_inventory: Literal[False] = False
    supplier_claim_approved: Literal[False] = False
