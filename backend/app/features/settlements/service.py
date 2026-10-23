"""Internally verified credit reconciliation, not bank/supplier integration.

Receipts reserve expected credit while pending and count as recovered only when
reviewed by a separate user. A terms-row lock serializes reservation & review.
"""
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.settlements.model import ClaimCreditTerms, CreditReceipt, CreditReceiptReview
from app.features.settlements.repository import scoped_claim, terms_for_claim, receipts_for_terms
from app.features.settlements.schema import CreditSummaryResponse


class SettlementMissing(Exception):
    pass


class SettlementConflict(Exception):
    pass


class SettlementForbidden(Exception):
    pass


async def _commit(db: AsyncSession, obj):
    await db.commit()
    await db.refresh(obj)
    return obj


async def _fail(db, exc: Exception):
    await db.rollback()
    if isinstance(exc, IntegrityError) and getattr(exc.orig, "sqlstate", None) == "23505":
        raise SettlementConflict("Duplicate credit terms or receipt") from exc
    raise exc


async def create_credit_terms(db: AsyncSession, org_id: UUID, user_id: UUID, claim_id: UUID, payload):
    try:
        claim = await scoped_claim(db, org_id, claim_id, lock=True)
        if claim is None:
            raise SettlementMissing
        if claim.status not in {"accepted", "partially_accepted"} or claim.accepted_quantity <= 0:
            raise SettlementConflict("A recorded supplier outcome with accepted quantity is required")
        current = await terms_for_claim(db, claim_id)
        if current:
            if (current.currency != payload.currency or current.unit_price_minor != payload.unit_price_minor
                    or current.note != payload.note):
                raise SettlementConflict("Existing credit terms are immutable")
            await db.commit()
            return current
        expected = claim.accepted_quantity * payload.unit_price_minor
        row = ClaimCreditTerms(
            claim_id=claim.id, recorded_by_user_id=user_id,
            accepted_quantity=claim.accepted_quantity, currency=payload.currency,
            unit_price_minor=payload.unit_price_minor, expected_minor=expected, note=payload.note,
        )
        db.add(row)
        return await _commit(db, row)
    except Exception as exc:
        await _fail(db, exc)


async def add_credit_receipt(db: AsyncSession, org_id: UUID, user_id: UUID, claim_id: UUID, payload, key: str):
    try:
        claim = await scoped_claim(db, org_id, claim_id)
        if claim is None:
            raise SettlementMissing
        terms = await terms_for_claim(db, claim_id, lock=True)
        if terms is None:
            raise SettlementConflict("Record credit terms before submitting a receipt")
        old = await db.scalar(select(CreditReceipt).where(
            CreditReceipt.terms_id == terms.id, CreditReceipt.idempotency_key == key,
        ))
        if old:
            if (old.amount_minor != payload.amount_minor or old.reference != payload.reference
                    or old.note != payload.note):
                raise SettlementConflict("Idempotency key reused with different data")
            await db.commit()
            return old
        rows = await receipts_for_terms(db, terms.id)
        reserved = sum(r.amount_minor for r in rows if r.status != "rejected")
        if payload.amount_minor > terms.expected_minor - reserved:
            raise SettlementConflict("Credit receipt exceeds unallocated expected credit")
        row = CreditReceipt(
            terms_id=terms.id, submitted_by_user_id=user_id,
            idempotency_key=key, amount_minor=payload.amount_minor,
            reference=payload.reference, note=payload.note,
        )
        db.add(row)
        return await _commit(db, row)
    except Exception as exc:
        await _fail(db, exc)


async def review_credit_receipt(db: AsyncSession, org_id: UUID, user_id: UUID,
                                claim_id: UUID, receipt_id: UUID, payload):
    try:
        claim = await scoped_claim(db, org_id, claim_id)
        if claim is None:
            raise SettlementMissing
        terms = await terms_for_claim(db, claim_id, lock=True)
        if terms is None:
            raise SettlementMissing
        # Lock ordering: terms -> receipt. All financial writers lock terms first.
        row = await db.scalar(select(CreditReceipt).where(
            CreditReceipt.id == receipt_id, CreditReceipt.terms_id == terms.id,
        ).with_for_update())
        if row is None:
            raise SettlementMissing
        if row.submitted_by_user_id == user_id:
            raise SettlementForbidden("Receipt submitter cannot approve or reject own receipt")
        if row.status != "pending":
            raise SettlementConflict("Receipt already reviewed")
        row.status = payload.decision
        db.add(CreditReceiptReview(
            receipt_id=row.id, reviewed_by_user_id=user_id,
            decision=payload.decision, reason=payload.reason,
        ))
        return await _commit(db, row)
    except Exception as exc:
        await _fail(db, exc)


async def list_credit_receipts(db: AsyncSession, org_id: UUID, claim_id: UUID, limit: int, offset: int):
    claim = await scoped_claim(db, org_id, claim_id)
    if claim is None:
        raise SettlementMissing
    terms = await terms_for_claim(db, claim_id)
    if terms is None:
        raise SettlementMissing
    stmt = (select(CreditReceipt)
            .where(CreditReceipt.terms_id == terms.id)
            .order_by(CreditReceipt.created_at, CreditReceipt.id)
            .limit(limit).offset(offset))
    return (await db.scalars(stmt)).all()


async def credit_summary(db: AsyncSession, org_id: UUID, claim_id: UUID):
    claim = await scoped_claim(db, org_id, claim_id)
    if claim is None:
        raise SettlementMissing
    terms = await terms_for_claim(db, claim_id)
    if terms is None:
        raise SettlementMissing
    values = (await db.execute(select(
        func.coalesce(func.sum(case(
            (CreditReceipt.status == "approved", CreditReceipt.amount_minor), else_=0
        )), 0),
        func.coalesce(func.sum(case(
            (CreditReceipt.status == "pending", CreditReceipt.amount_minor), else_=0
        )), 0),
    ).where(CreditReceipt.terms_id == terms.id))).one()
    approved, pending = int(values[0]), int(values[1])
    expected = terms.expected_minor
    remaining = expected - approved - pending
    status = ("fully_reconciled_internal" if approved == expected else
              "partially_reconciled" if approved else "unsettled")
    return CreditSummaryResponse(
        claim_id=claim.id, currency=terms.currency, accepted_quantity=terms.accepted_quantity,
        unit_price_minor=terms.unit_price_minor, expected_minor=expected,
        approved_recorded_minor=approved, pending_review_minor=pending,
        remaining_unrecorded_minor=remaining, outstanding_unapproved_minor=expected-approved,
        reconciliation_status=status,
    )
