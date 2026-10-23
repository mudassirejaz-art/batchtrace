"""Strict verification API schemas. No claimable-stock or supplier-approval promises."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VerificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lot_id: UUID
    import_id: UUID
    counted_quantity: int = Field(ge=0, le=2147483647)
    note: str = Field(min_length=10, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 10:
            raise ValueError("Note must contain at least 10 non-space characters")
        return cleaned


class VerificationReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=10, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 10:
            raise ValueError("Reason must contain at least 10 non-space characters")
        return cleaned


class VerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    lot_id: UUID
    import_id: UUID
    snapshot_row_id: UUID
    policy_id: UUID
    submitted_by_user_id: UUID
    observed_quantity: int
    counted_quantity: int
    note: str
    status: Literal["pending", "approved", "rejected"]
    created_at: datetime
    # A physically checked number is not reserved, return-eligible, or supplier-approved.
    is_supplier_claim: Literal[False] = False
    changes_inventory_balance: Literal[False] = False


class DecisionResponse(BaseModel):
    verification: VerificationResponse
    decision_id: UUID
    reviewed_by_user_id: UUID
    decision: Literal["approved", "rejected"]
    reason: str
    reviewed_at: datetime
