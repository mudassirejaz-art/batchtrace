from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9][A-Z0-9._-]*$")
    name: str = Field(min_length=1, max_length=200)

    @field_validator("sku", mode="before")
    @classmethod
    def clean_sku(cls, value: str) -> str:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[A-Z0-9][A-Z0-9._-]*$")
    name: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("sku", mode="before")
    @classmethod
    def clean_sku(cls, value: str | None) -> str | None:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    sku: str
    name: str
    created_at: datetime
