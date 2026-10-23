"""Transactional physical count and independent human review. Never reserves stock."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.recovery.service import classify_window
from app.features.recovery.repository import policies_for_suppliers
from app.features.verifications.model import StockVerification, VerificationDecision
from app.features.verifications.repository import (
    by_id, by_idempotency, latest_snapshot, locked_lot,
)


class VerificationNotFound(Exception):
    pass


class VerificationConflict(Exception):
    pass


class ReviewForbidden(Exception):
    pass


async def _open_policy(db, org_id, lot, today):
    policies = await policies_for_suppliers(db, org_id, today, {lot.supplier_id})
    policy = policies.get(lot.supplier_id)
    window, _, _ = classify_window(policy, lot.expiry_date, today)
    if window != "window_open":
        raise VerificationConflict(f"Supplier return window is {window}")
    return policy


async def submit_verification(
    db: AsyncSession, org_id: UUID, user_id: UUID, payload, idempotency_key: str,
) -> StockVerification:
    today = datetime.now(timezone.utc).date()
    try:
        lot = await locked_lot(db, org_id, payload.lot_id)
        if lot is None:
            raise VerificationNotFound
        previous = await by_idempotency(db, org_id, idempotency_key)
        if previous is not None:
            if (
                previous.lot_id != payload.lot_id
                or previous.import_id != payload.import_id
                or previous.counted_quantity != payload.counted_quantity
                or previous.note != payload.note
            ):
                raise VerificationConflict("Idempotency key reused with different request")
            await db.commit()  # release lot lock; session does not expire on commit
            return previous

        observation = await latest_snapshot(db, org_id, lot.id, today)
        if observation is None:
            raise VerificationConflict("No committed observation available for lot")
        snapshot, imported = observation
        if imported.id != payload.import_id:
            raise VerificationConflict("Import is not the latest observation for this lot")
        if snapshot.observed_quantity == 0:
            raise VerificationConflict("Latest observed quantity is zero")

        # A newer snapshot cannot override a pending count that has not been reviewed.
        existing = await db.scalar(select(StockVerification.id).where(
            StockVerification.organization_id == org_id,
            StockVerification.lot_id == lot.id,
            StockVerification.status == "pending",
        ))
        if existing:
            raise VerificationConflict("Lot already has a pending verification")

        policy = await _open_policy(db, org_id, lot, today)
        verification = StockVerification(
            organization_id=org_id, lot_id=lot.id,
            import_id=imported.id, snapshot_row_id=snapshot.id,
            policy_id=policy.id, submitted_by_user_id=user_id,
            idempotency_key=idempotency_key,
            observed_quantity=snapshot.observed_quantity,
            counted_quantity=payload.counted_quantity,
            note=payload.note, status="pending",
        )
        db.add(verification)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise VerificationConflict("Verification already exists for import and lot") from exc
        raise
    except Exception:
        await db.rollback()
        raise
    await db.refresh(verification)
    return verification


async def review_verification(
    db: AsyncSession, org_id: UUID, user_id: UUID, verification_id: UUID, payload,
):
    today = datetime.now(timezone.utc).date()
    try:
        record = await by_id(db, org_id, verification_id, lock=True)
        if record is None:
            raise VerificationNotFound
        if record.submitted_by_user_id == user_id:
            raise ReviewForbidden("Creator cannot approve or reject own submission")
        if record.status != "pending":
            raise VerificationConflict("Verification already reviewed")
        if payload.decision == "approved":
            lot = await locked_lot(db, org_id, record.lot_id)
            if lot is None:
                raise VerificationConflict("Lot no longer exists")
            observation = await latest_snapshot(db, org_id, record.lot_id, today)
            if observation is None or observation[0].id != record.snapshot_row_id:
                raise VerificationConflict("New observation exists; submit a new verification")
            policy = await _open_policy(db, org_id, lot, today)
            if policy.id != record.policy_id:
                raise VerificationConflict("Supplier policy changed; submit a new verification")
        record.status = payload.decision
        decision = VerificationDecision(
            verification_id=record.id, reviewer_user_id=user_id,
            decision=payload.decision, reason=payload.reason,
        )
        db.add(decision)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise VerificationConflict("Verification already reviewed") from exc
        raise
    except Exception:
        await db.rollback()
        raise
    await db.refresh(record)
    await db.refresh(decision)
    return record, decision
