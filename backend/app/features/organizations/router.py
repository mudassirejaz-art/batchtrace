from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.auth.dependencies import get_current_user
from app.features.auth.model import User
from app.features.organizations.repository import list_user_organizations

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str


@router.get("/me", response_model=list[OrganizationResponse])
async def my_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = await list_user_organizations(db, current_user.id)
    return [
        OrganizationResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            role=role,
        )
        for org, role in rows
    ]
