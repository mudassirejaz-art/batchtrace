"""Public contracts for a lot record. A lot is NOT an inventory balance."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    supplier_id: UUID
    batch_number: str = Field(min_length=1, max_length=100)
    expiry_date: date

    @field_validator("batch_number", mode="before")
    @classmethod
    def normalize_batch_number(cls, value: str) -> str:
        # Preserve internal characters; trim and normalize capitalization only.
        return value.strip().upper() if isinstance(value, str) else value


class LotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    product_id: UUID
    supplier_id: UUID
    batch_number: str
    expiry_date: date
    created_at: datetime


class ExpiryWatchItem(LotResponse):
    days_until_expiry: int = Field(ge=0)
    urgency: Literal["due_today", "upcoming"]
