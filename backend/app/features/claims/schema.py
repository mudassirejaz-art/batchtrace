"""Strict claim and staff-recorded supplier decision contracts."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NoteBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(min_length=10, max_length=500)

    @field_validator("note")
    @classmethod
    def trim_note(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("note must contain at least ten non-whitespace characters")
        return value


class ClaimCreate(NoteBase):
    verification_id: UUID
    quantity: int = Field(ge=1, le=2147483647)


class ClaimNote(NoteBase):
    pass


class SupplierResponseCreate(NoteBase):
    accepted_quantity: int = Field(ge=0, le=2147483647)
    rejected_quantity: int = Field(ge=0, le=2147483647)

    @model_validator(mode="after")
    def nonzero_response(self):
        if self.accepted_quantity + self.rejected_quantity == 0:
            raise ValueError("At least one unit must be accounted for")
        return self


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    verification_id: UUID
    submitted_by_user_id: UUID
    quantity: int
    note: str
    status: Literal['draft','approved','dispatched','accepted','rejected','partially_accepted']
    accepted_quantity: int
    rejected_quantity: int
    created_at: datetime
    is_external_supplier_confirmation: Literal[False] = False
    changes_inventory_balance: Literal[False] = False


class ClaimEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    claim_id: UUID
    actor_user_id: UUID
    event_type: Literal['created','approved','dispatched','supplier_response_recorded']
    note: str
    created_at: datetime


class ClaimDetailResponse(ClaimResponse):
    events: list[ClaimEventResponse]
