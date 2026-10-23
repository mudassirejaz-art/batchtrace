"""Add physical count attestations and separate review decisions; no existing table changes.

Revision ID: b4d7f0c9e831
Revises: a7e65ca94f10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b4d7f0c9e831"
down_revision: Union[str, Sequence[str], None] = "a7e65ca94f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stock_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_row_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("observed_quantity", sa.Integer(), nullable=False),
        sa.Column("counted_quantity", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=12), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["import_id"], ["inventory_imports.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_row_id"], ["inventory_snapshot_rows.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["policy_id"], ["return_policy_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_verification_idempotency"),
        sa.UniqueConstraint("organization_id", "import_id", "lot_id", name="uq_verification_snapshot_lot"),
        sa.CheckConstraint("counted_quantity >= 0", name="ck_verification_count_nonnegative"),
        sa.CheckConstraint("observed_quantity >= 0", name="ck_verification_observed_nonnegative"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_verification_status"),
    )
    op.create_table(
        "verification_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=12), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["verification_id"], ["stock_verifications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("verification_id", name="uq_verification_single_decision"),
        sa.CheckConstraint("decision IN ('approved', 'rejected')", name="ck_verification_decision"),
    )


def downgrade() -> None:
    op.drop_table("verification_decisions")
    op.drop_table("stock_verifications")
