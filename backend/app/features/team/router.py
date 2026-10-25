"""Organization-scoped membership management. No mail, third-party APIs or schema changes."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.features.auth.model import User
from app.features.organizations.dependencies import require_read_membership
from app.features.organizations.membership_model import OrganizationMembership
from app.features.organizations.model import Organization
from app.features.team.schema import TeamMemberCreate, TeamMemberResponse, TeamRoleUpdate

router = APIRouter(prefix="/api/v1/organizations/{organization_id}/team", tags=["Team"])
Db = Annotated[AsyncSession, Depends(get_db)]
Reader = Annotated[OrganizationMembership, Depends(require_read_membership)]


def serialize(membership: OrganizationMembership, user: User) -> TeamMemberResponse:
    return TeamMemberResponse(
        membership_id=membership.id, user_id=membership.user_id,
        email=user.email, role=membership.role, joined_at=membership.created_at,
    )


def can_manage(actor_role: str, target_role: str) -> bool:
    return actor_role == "owner" or (actor_role == "admin" and target_role in {"staff", "viewer"})


async def lock_and_authorize(db: AsyncSession, org_id: UUID, user_id: UUID) -> OrganizationMembership:
    # Organization row is the shared concurrency lock for all team mutations.
    organization = await db.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
    if organization is None:
        raise HTTPException(404, "Organization not found")
    actor = await db.scalar(select(OrganizationMembership).where(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user_id,
    ).execution_options(populate_existing=True))
    if actor is None:
        raise HTTPException(404, "Organization not found")
    if actor.role not in {"owner", "admin"}:
        raise HTTPException(403, "Owner or admin role required")
    return actor


@router.get("", response_model=list[TeamMemberResponse])
async def list_team(organization_id: UUID, membership: Reader, db: Db):
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Team directory is restricted to owners/admins")
    result = await db.execute(
        select(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(OrganizationMembership.organization_id == organization_id)
        .order_by(User.email)
    )
    return [serialize(member, user) for member, user in result.all()]


@router.post("", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_team_member(organization_id: UUID, payload: TeamMemberCreate, membership: Reader, db: Db):
    try:
        actor = await lock_and_authorize(db, organization_id, membership.user_id)
        if not can_manage(actor.role, payload.role):
            raise HTTPException(403, "Admins may add staff or viewers only")
        target = await db.scalar(select(User).where(User.email == str(payload.email), User.is_active.is_(True)))
        if target is None:
            raise HTTPException(404, "User must register an account first")
        exists = await db.scalar(select(OrganizationMembership.id).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == target.id,
        ))
        if exists:
            raise HTTPException(409, "User is already a team member")
        member = OrganizationMembership(organization_id=organization_id, user_id=target.id, role=payload.role)
        db.add(member)
        await db.flush()
        response = serialize(member, target)
        await db.commit()
        return response
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Membership conflict") from None
    except Exception:
        await db.rollback()
        raise


@router.patch("/{member_id}", response_model=TeamMemberResponse)
async def update_member_role(organization_id: UUID, member_id: UUID, payload: TeamRoleUpdate, membership: Reader, db: Db):
    try:
        actor = await lock_and_authorize(db, organization_id, membership.user_id)
        member = await db.scalar(select(OrganizationMembership).where(
            OrganizationMembership.id == member_id,
            OrganizationMembership.organization_id == organization_id,
        ))
        if member is None:
            raise HTTPException(404, "Team member not found")
        if not can_manage(actor.role, member.role) or not can_manage(actor.role, payload.role):
            raise HTTPException(403, "Insufficient permissions to modify this role")
        if member.role == "owner":
            raise HTTPException(403, "Owner role cannot be changed here")
        if member.user_id == actor.user_id:
            raise HTTPException(403, "Cannot modify your own membership")
        member.role = payload.role
        user = await db.get(User, member.user_id)
        await db.flush()
        response = serialize(member, user)
        await db.commit()
        return response
    except Exception:
        await db.rollback()
        raise


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(organization_id: UUID, member_id: UUID, membership: Reader, db: Db):
    try:
        actor = await lock_and_authorize(db, organization_id, membership.user_id)
        member = await db.scalar(select(OrganizationMembership).where(
            OrganizationMembership.id == member_id,
            OrganizationMembership.organization_id == organization_id,
        ))
        if member is None:
            raise HTTPException(404, "Team member not found")
        if member.user_id == actor.user_id or member.role == "owner":
            raise HTTPException(403, "Cannot remove yourself or an owner")
        if not can_manage(actor.role, member.role):
            raise HTTPException(403, "Insufficient permissions to remove this member")
        # Existing review/credit evidence refers to the User, not this membership;
        # removing access must not erase historical actions.
        await db.delete(member)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
