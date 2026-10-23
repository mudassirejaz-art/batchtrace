"""Internal return claims, reserved verification quantities and append-only events."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReturnClaim(Base):
    __tablename__ = "return_claims"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_claim_org_idempotency"),
        CheckConstraint("quantity > 0", name="ck_claim_quantity_positive"),
        CheckConstraint(
            "status IN ('draft','approved','dispatched','accepted','rejected','partially_accepted')",
            name="ck_claim_status",
        ),
        CheckConstraint("accepted_quantity >= 0 AND rejected_quantity >= 0", name="ck_claim_response_nonnegative"),
        CheckConstraint("accepted_quantity + rejected_quantity <= quantity", name="ck_claim_response_bounded"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False,
    )
    verification_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stock_verifications.id", ondelete="RESTRICT"), nullable=False,
    )
    submitted_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(24), server_default=text("'draft'"), nullable=False)
    accepted_quantity: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    rejected_quantity: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClaimEvent(Base):
    __tablename__ = "claim_events"
    __table_args__ = (
        UniqueConstraint("claim_id", "event_type", name="uq_claim_event_once"),
        CheckConstraint(
            "event_type IN ('created','approved','dispatched','supplier_response_recorded')",
            name="ck_claim_event_type",
        ),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("return_claims.id", ondelete="RESTRICT"), nullable=False,
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(28), nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
