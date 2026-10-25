"""Strict team API data contracts."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["owner", "admin", "staff", "viewer"]


class TeamMemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    role: Literal["admin", "staff", "viewer"]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class TeamRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["admin", "staff", "viewer"]


class TeamMemberResponse(BaseModel):
    membership_id: UUID
    user_id: UUID
    email: EmailStr
    role: Role
    joined_at: datetime
