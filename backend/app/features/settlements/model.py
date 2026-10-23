"""Immutable expected-credit basis and internally reviewed credit receipts.

Amounts are integer currency MINOR units, never float. No provider or bank integration.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClaimCreditTerms(Base):
    __tablename__ = "claim_credit_terms"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_credit_terms_claim"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_credit_currency"),
        CheckConstraint("accepted_quantity > 0", name="ck_credit_accepted_positive"),
        CheckConstraint("unit_price_minor BETWEEN 1 AND 100000000", name="ck_credit_price_range"),
        CheckConstraint("expected_minor = accepted_quantity * unit_price_minor", name="ck_credit_expected_calculated"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("return_claims.id", ondelete="RESTRICT"), nullable=False,
    )
    recorded_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    accepted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class CreditReceipt(Base):
    __tablename__ = "credit_receipts"
    __table_args__ = (
        UniqueConstraint("terms_id", "idempotency_key", name="uq_credit_receipt_key"),
        CheckConstraint("amount_minor > 0", name="ck_receipt_amount_positive"),
        CheckConstraint("status IN ('pending','approved','rejected')", name="ck_receipt_status"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    terms_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("claim_credit_terms.id", ondelete="RESTRICT"), nullable=False,
    )
    submitted_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference: Mapped[str] = mapped_column(String(100), nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(12), server_default=text("'pending'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class CreditReceiptReview(Base):
    __tablename__ = "credit_receipt_reviews"
    __table_args__ = (
        UniqueConstraint("receipt_id", name="uq_credit_receipt_review_once"),
        CheckConstraint("decision IN ('approved','rejected')", name="ck_credit_review_decision"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("credit_receipts.id", ondelete="RESTRICT"), nullable=False,
    )
    reviewed_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(12), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
