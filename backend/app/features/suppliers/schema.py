from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Z0-9][A-Z0-9._-]*$")
    name: str = Field(min_length=1, max_length=160)

    @field_validator("code", mode="before")
    @classmethod
    def clean_code(cls, value: str) -> str:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(default=None, min_length=1, max_length=50, pattern=r"^[A-Z0-9][A-Z0-9._-]*$")
    name: str | None = Field(default=None, min_length=1, max_length=160)

    @field_validator("code", mode="before")
    @classmethod
    def clean_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    code: str
    name: str
    created_at: datetime
