from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.organizations.membership_model import OrganizationMembership
from app.features.organizations.model import Organization


async def list_user_organizations(db: AsyncSession, user_id: UUID):
    stmt = (
        select(Organization, OrganizationMembership.role)
        .join(
            OrganizationMembership,
            OrganizationMembership.organization_id == Organization.id,
        )
        .where(OrganizationMembership.user_id == user_id)
        .order_by(Organization.name)
    )
    result = await db.execute(stmt)
    return result.all()
