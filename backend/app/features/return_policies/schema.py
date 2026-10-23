"""Supplier-level, versioned date-window rules; NOT final claim approval."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: UUID
    days_before_expiry: int = Field(ge=0, le=3650)
    days_after_expiry: int = Field(ge=0, le=3650)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def check_effective_range(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on/after effective_from")
        return self


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    supplier_id: UUID
    version: int
    days_before_expiry: int
    days_after_expiry: int
    effective_from: date
    effective_to: date | None
    created_at: datetime


class ReturnWindowResponse(BaseModel):
    lot_id: UUID
    supplier_id: UUID
    as_of: date
    expiry_date: date
    status: Literal["no_policy", "policy_expired", "not_yet_open", "window_open", "window_closed"]
    policy_id: UUID | None = None
    policy_version: int | None = None
    return_opens_on: date | None = None
    return_closes_on: date | None = None
    date_window_only: Literal[True] = True
    # Neither stock quantity nor supplier claim approval is verified by this endpoint.
