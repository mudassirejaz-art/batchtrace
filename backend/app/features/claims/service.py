"""Internal claim workflow. Does NOT contact suppliers or alter physical stock."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.claims.model import ReturnClaim, ClaimEvent
from app.features.claims.repository import (
    allocated_quantity, claim_by_id, claim_by_key, locked_verification,
)
from app.features.lots.model import Lot
from app.features.recovery.repository import policies_for_suppliers
from app.features.recovery.service import classify_window
from app.features.verifications.repository import latest_snapshot
from sqlalchemy import select


class ClaimNotFound(Exception):
    pass


class ClaimConflict(Exception):
    pass


class ClaimForbidden(Exception):
    pass


async def _verify_current_source(db: AsyncSession, org_id: UUID, verified):
    today = datetime.now(timezone.utc).date()
    lot = await db.scalar(select(Lot).where(
        Lot.id == verified.lot_id, Lot.organization_id == org_id,
    ))
    if lot is None:
        raise ClaimConflict("Verified lot is unavailable")
    latest = await latest_snapshot(db, org_id, lot.id, today)
    if latest is None or latest[0].id != verified.snapshot_row_id:
        raise ClaimConflict("Stock source changed: a new physical verification is required")
    policy = (await policies_for_suppliers(db, org_id, today, {lot.supplier_id})).get(lot.supplier_id)
    window, _, _ = classify_window(policy, lot.expiry_date, today)
    if window != "window_open" or policy is None or policy.id != verified.policy_id:
        raise ClaimConflict("Supplier policy or return window changed: re-verify first")


async def _event(db: AsyncSession, claim: ReturnClaim, actor: UUID, kind: str, note: str):
    db.add(ClaimEvent(claim_id=claim.id, actor_user_id=actor, event_type=kind, note=note))


async def _finish(db: AsyncSession, record: ReturnClaim):
    await db.commit()
    await db.refresh(record)
    return record


async def create_claim(db: AsyncSession, org_id: UUID, user_id: UUID, payload, key: str):
    try:
        verified = await locked_verification(db, org_id, payload.verification_id)
        if verified is None:
            raise ClaimNotFound
        previous = await claim_by_key(db, org_id, key)
        if previous:
            if (previous.verification_id != payload.verification_id
                or previous.quantity != payload.quantity or previous.note != payload.note):
                raise ClaimConflict("Idempotency key reused with a different request")
            await db.commit()
            return previous
        if verified.status != "approved" or verified.counted_quantity <= 0:
            raise ClaimConflict("An approved, positive physical verification is required")
        await _verify_current_source(db, org_id, verified)
        reserved = await allocated_quantity(db, verified.id)
        if payload.quantity > verified.counted_quantity - reserved:
            raise ClaimConflict("Requested units exceed unallocated verified quantity")
        record = ReturnClaim(
            organization_id=org_id, verification_id=verified.id,
            submitted_by_user_id=user_id, idempotency_key=key,
            quantity=payload.quantity, note=payload.note,
        )
        db.add(record)
        await db.flush()
        await _event(db, record, user_id, "created", payload.note)
        return await _finish(db, record)
    except IntegrityError as exc:
        await db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise ClaimConflict("Claim or event already exists") from exc
        raise
    except Exception:
        await db.rollback()
        raise


async def advance_claim(db: AsyncSession, org_id: UUID, user_id: UUID,
                        claim_id: UUID, action: str, note: str,
                        *, accepted: int = 0, rejected: int = 0):
    try:
        record = await claim_by_id(db, org_id, claim_id, lock=True)
        if record is None:
            raise ClaimNotFound
        required = {"approve": "draft", "dispatch": "approved", "supplier_response": "dispatched"}
        if record.status != required[action]:
            raise ClaimConflict(f"Cannot {action} claim in status {record.status}")
        if action == "approve":
            if record.submitted_by_user_id == user_id:
                raise ClaimForbidden("Claim creator cannot approve own claim")
            verified = await locked_verification(db, org_id, record.verification_id)
            if verified is None or verified.status != "approved":
                raise ClaimConflict("Physical verification is no longer approved")
            await _verify_current_source(db, org_id, verified)
            record.status = "approved"
            kind = "approved"
        elif action == "dispatch":
            record.status = "dispatched"
            kind = "dispatched"
        else:
            if accepted + rejected != record.quantity:
                raise ClaimConflict("Supplier response must account for all claimed units")
            record.accepted_quantity = accepted
            record.rejected_quantity = rejected
            record.status = (
                "accepted" if accepted == record.quantity else
                "rejected" if rejected == record.quantity else "partially_accepted"
            )
            kind = "supplier_response_recorded"
        await _event(db, record, user_id, kind, note)
        return await _finish(db, record)
    except IntegrityError as exc:
        await db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise ClaimConflict("Claim transition already recorded") from exc
        raise
    except Exception:
        await db.rollback()
        raise
