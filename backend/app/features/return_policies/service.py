"""Append-only supplier policy versions and explainable date-window evaluation."""
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.lots.repository import get_lot
from app.features.return_policies.model import ReturnPolicyVersion
from app.features.return_policies.repository import (
    effective_policy, last_policy, lock_supplier,
)
from app.features.return_policies.schema import PolicyCreate, ReturnWindowResponse


class UnknownSupplier(Exception):
    pass


class PolicyConflict(Exception):
    pass


class UnknownLot(Exception):
    pass


class PolicyDateOverflow(Exception):
    pass


async def create_policy(db: AsyncSession, org_id: UUID, data: PolicyCreate) -> ReturnPolicyVersion:
    # Membership validation has already run in the route dependency.
    # Row-lock supplier before reading latest version, to prevent version races.
    try:
        supplier = await lock_supplier(db, org_id, data.supplier_id)
        if supplier is None:
            raise UnknownSupplier
        previous = await last_policy(db, org_id, data.supplier_id)
        if previous is not None and data.effective_from <= previous.effective_from:
            raise PolicyConflict("New version must start after previous effective_from")

        policy = ReturnPolicyVersion(
            organization_id=org_id,
            supplier_id=data.supplier_id,
            version=(previous.version + 1 if previous else 1),
            days_before_expiry=data.days_before_expiry,
            days_after_expiry=data.days_after_expiry,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
        )
        db.add(policy)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise PolicyConflict("Duplicate policy version") from exc
        raise
    except Exception:
        await db.rollback()
        raise
    await db.refresh(policy)
    return policy


async def evaluate_lot(
    db: AsyncSession, org_id: UUID, lot_id: UUID, as_of: date,
) -> ReturnWindowResponse:
    lot = await get_lot(db, org_id, lot_id)
    if lot is None:
        raise UnknownLot

    base = dict(lot_id=lot.id, supplier_id=lot.supplier_id,
                as_of=as_of, expiry_date=lot.expiry_date)
    policy = await effective_policy(db, org_id, lot.supplier_id, as_of)
    if policy is None:
        return ReturnWindowResponse(**base, status="no_policy")

    if policy.effective_to is not None and as_of > policy.effective_to:
        return ReturnWindowResponse(**base, status="policy_expired",
                                    policy_id=policy.id, policy_version=policy.version)

    try:
        opens = lot.expiry_date - timedelta(days=policy.days_before_expiry)
        closes = lot.expiry_date + timedelta(days=policy.days_after_expiry)
    except OverflowError as exc:
        raise PolicyDateOverflow from exc

    state = ("not_yet_open" if as_of < opens else
             "window_closed" if as_of > closes else "window_open")
    return ReturnWindowResponse(
        **base, status=state, policy_id=policy.id, policy_version=policy.version,
        return_opens_on=opens, return_closes_on=closes,
    )
