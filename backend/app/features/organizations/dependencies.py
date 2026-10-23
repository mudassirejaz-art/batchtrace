"""Organization membership authorization for organization-scoped routes."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.auth.dependencies import get_current_user
from app.features.auth.model import User
from app.features.organizations.membership_model import OrganizationMembership


async def require_read_membership(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationMembership:
    # Check user+organization together; avoid leaking whether other orgs exist.
    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == current_user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return membership


async def require_write_membership(
    membership: Annotated[OrganizationMembership, Depends(require_read_membership)],
) -> OrganizationMembership:
    if membership.role not in {"owner", "admin", "staff"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient organization permissions",
        )
    return membership
