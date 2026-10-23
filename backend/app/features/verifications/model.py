"""Physical-count attestations and append-only reviewer decisions."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Integer, String,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StockVerification(Base):
    __tablename__ = "stock_verifications"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_verification_idempotency"),
        UniqueConstraint("organization_id", "import_id", "lot_id", name="uq_verification_snapshot_lot"),
        CheckConstraint("counted_quantity >= 0", name="ck_verification_count_nonnegative"),
        CheckConstraint("observed_quantity >= 0", name="ck_verification_observed_nonnegative"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_verification_status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lots.id", ondelete="RESTRICT"), nullable=False
    )
    import_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("inventory_imports.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_row_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("inventory_snapshot_rows.id", ondelete="RESTRICT"), nullable=False
    )
    policy_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("return_policy_versions.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    observed_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    counted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(12), server_default=text("'pending'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VerificationDecision(Base):
    __tablename__ = "verification_decisions"
    __table_args__ = (
        UniqueConstraint("verification_id", name="uq_verification_single_decision"),
        CheckConstraint("decision IN ('approved', 'rejected')", name="ck_verification_decision"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    verification_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stock_verifications.id", ondelete="RESTRICT"), nullable=False
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(12), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
