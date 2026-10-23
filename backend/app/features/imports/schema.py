"""Contracts explicitly label imported counts as unverified observations."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RowError(BaseModel):
    line: int
    code: str
    message: str


class PreviewResponse(BaseModel):
    valid: bool
    observed_on: date
    total_rows: int
    valid_rows: int
    errors: list[RowError]
    fingerprint: str | None = None
    snapshot_only: Literal[True] = True


class ImportResponse(BaseModel):
    id: UUID
    organization_id: UUID
    observed_on: date
    filename: str
    row_count: int
    content_sha256: str
    created_at: datetime
    snapshot_only: Literal[True] = True


class SnapshotRowResponse(BaseModel):
    lot_id: UUID
    observed_quantity: int = Field(ge=0)


class ImportDetailResponse(ImportResponse):
    rows: list[SnapshotRowResponse]
