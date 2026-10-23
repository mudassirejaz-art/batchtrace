"""Credit reconciliation schemas, with amounts exclusively in minor currency units."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Note(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(min_length=10, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str):
        value = value.strip()
        if len(value) < 10:
            raise ValueError("At least ten non-whitespace characters required")
        return value


class CreditTermsCreate(Note):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    unit_price_minor: int = Field(ge=1, le=100_000_000)


class CreditReceiptCreate(Note):
    amount_minor: int = Field(ge=1, le=900_000_000_000_000_000)
    reference: str = Field(min_length=3, max_length=100)

    @field_validator("reference")
    @classmethod
    def normalize_reference(cls, value: str):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Reference must have at least three characters")
        return value


class ReceiptReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=10, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str):
        value = value.strip()
        if len(value) < 10:
            raise ValueError("At least ten non-whitespace characters required")
        return value


class CreditTermsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    claim_id: UUID
    recorded_by_user_id: UUID
    currency: str
    accepted_quantity: int
    unit_price_minor: int
    expected_minor: int
    note: str
    created_at: datetime
    externally_verified: Literal[False] = False


class CreditReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    terms_id: UUID
    submitted_by_user_id: UUID
    amount_minor: int
    reference: str
    note: str
    status: Literal["pending", "approved", "rejected"]
    created_at: datetime
    is_bank_confirmed: Literal[False] = False


class CreditSummaryResponse(BaseModel):
    claim_id: UUID
    currency: str
    accepted_quantity: int
    unit_price_minor: int
    expected_minor: int
    approved_recorded_minor: int
    pending_review_minor: int
    remaining_unrecorded_minor: int
    outstanding_unapproved_minor: int
    reconciliation_status: Literal["unsettled", "partially_reconciled", "fully_reconciled_internal"]
    is_bank_verified: Literal[False] = False
    changes_inventory_balance: Literal[False] = False
