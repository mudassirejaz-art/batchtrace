"""Add internal credit reconciliation evidence. Existing tables are unchanged.

Revision ID: d6f20a718c43
Revises: c5e81d0a624f
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d6f20a718c43"
down_revision: Union[str, Sequence[str], None] = "c5e81d0a624f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "claim_credit_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("accepted_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("expected_minor", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["claim_id"], ["return_claims.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("claim_id", name="uq_credit_terms_claim"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_credit_currency"),
        sa.CheckConstraint("accepted_quantity > 0", name="ck_credit_accepted_positive"),
        sa.CheckConstraint("unit_price_minor BETWEEN 1 AND 100000000", name="ck_credit_price_range"),
        sa.CheckConstraint("expected_minor = accepted_quantity * unit_price_minor", name="ck_credit_expected_calculated"),
    )
    op.create_table(
        "credit_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("terms_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=12), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["terms_id"], ["claim_credit_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("terms_id", "idempotency_key", name="uq_credit_receipt_key"),
        sa.CheckConstraint("amount_minor > 0", name="ck_receipt_amount_positive"),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_receipt_status"),
    )
    op.create_table(
        "credit_receipt_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=12), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["receipt_id"], ["credit_receipts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("receipt_id", name="uq_credit_receipt_review_once"),
        sa.CheckConstraint("decision IN ('approved','rejected')", name="ck_credit_review_decision"),
    )


def downgrade() -> None:
    op.drop_table("credit_receipt_reviews")
    op.drop_table("credit_receipts")
    op.drop_table("claim_credit_terms")
