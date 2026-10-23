"""CSV preview, commit, and read-only snapshot APIs."""
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.imports.repository import get_import, list_import_rows, list_imports
from app.features.imports.schema import (
    ImportDetailResponse, ImportResponse, PreviewResponse, SnapshotRowResponse,
)
from app.features.imports.service import (
    MAX_BYTES, CsvInvalid, ImportAlreadyExists, PreviewMismatch,
    commit_csv, evaluate_csv,
)
from app.features.organizations.dependencies import (
    require_read_membership, require_write_membership,
)
from app.features.organizations.membership_model import OrganizationMembership

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/imports",
    tags=["Inventory snapshot imports"],
)
ReadMember = Annotated[OrganizationMembership, Depends(require_read_membership)]
WriteMember = Annotated[OrganizationMembership, Depends(require_write_membership)]
Db = Annotated[AsyncSession, Depends(get_db)]


async def _upload(file: UploadFile) -> tuple[str, bytes]:
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not filename.lower().endswith(".csv") or len(filename) > 200:
        raise HTTPException(status_code=422, detail="A .csv filename is required (max 200 characters)")
    blob = await file.read(MAX_BYTES + 1)
    await file.close()
    if len(blob) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV exceeds 2 MiB")
    return filename, blob


@router.post("/preview", response_model=PreviewResponse)
async def preview_route(
    organization_id: UUID, member: ReadMember, db: Db,
    file: Annotated[UploadFile, File()],
    observed_on: Annotated[date, Form()],
):
    _, blob = await _upload(file)
    try:
        preview, _ = await evaluate_csv(db, organization_id, observed_on, blob)
        return preview
    except CsvInvalid as exc:
        raise HTTPException(status_code=422, detail=exc.message) from None


@router.post("/commit", response_model=ImportResponse, status_code=201)
async def commit_route(
    organization_id: UUID, member: WriteMember, db: Db,
    file: Annotated[UploadFile, File()],
    observed_on: Annotated[date, Form()],
    preview_fingerprint: Annotated[str, Form(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")],
):
    filename, blob = await _upload(file)
    try:
        imported = await commit_csv(
            db, organization_id, observed_on, filename, blob, preview_fingerprint,
        )
        return ImportResponse.model_validate(imported, from_attributes=True)
    except CsvInvalid as exc:
        raise HTTPException(status_code=422, detail=exc.message) from None
    except PreviewMismatch:
        raise HTTPException(status_code=409, detail="CSV or observed_on differs from preview") from None
    except ImportAlreadyExists:
        raise HTTPException(status_code=409, detail="Identical snapshot already committed") from None


@router.get("", response_model=list[ImportResponse])
async def list_route(
    organization_id: UUID, member: ReadMember, db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return [ImportResponse.model_validate(record, from_attributes=True)
            for record in await list_imports(db, organization_id, limit, offset)]


@router.get("/{import_id}", response_model=ImportDetailResponse)
async def detail_route(
    organization_id: UUID, import_id: UUID, member: ReadMember, db: Db,
):
    record = await get_import(db, organization_id, import_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Import not found")
    rows = await list_import_rows(db, import_id)
    return ImportDetailResponse(
        **ImportResponse.model_validate(record, from_attributes=True).model_dump(),
        rows=[SnapshotRowResponse(lot_id=row.lot_id, observed_quantity=row.observed_quantity)
              for row in rows],
    )
