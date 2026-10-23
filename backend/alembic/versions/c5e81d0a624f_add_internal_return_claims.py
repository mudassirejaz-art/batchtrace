"""Create internal claims and immutable claim events. No existing-table modifications.

Revision ID: c5e81d0a624f
Revises: b4d7f0c9e831
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c5e81d0a624f"
down_revision: Union[str, Sequence[str], None] = "b4d7f0c9e831"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "return_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=24), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("accepted_quantity", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rejected_quantity", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["verification_id"], ["stock_verifications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_claim_org_idempotency"),
        sa.CheckConstraint("quantity > 0", name="ck_claim_quantity_positive"),
        sa.CheckConstraint("status IN ('draft','approved','dispatched','accepted','rejected','partially_accepted')", name="ck_claim_status"),
        sa.CheckConstraint("accepted_quantity >= 0 AND rejected_quantity >= 0", name="ck_claim_response_nonnegative"),
        sa.CheckConstraint("accepted_quantity + rejected_quantity <= quantity", name="ck_claim_response_bounded"),
    )
    op.create_table(
        "claim_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=28), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["claim_id"], ["return_claims.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("claim_id", "event_type", name="uq_claim_event_once"),
        sa.CheckConstraint("event_type IN ('created','approved','dispatched','supplier_response_recorded')", name="ck_claim_event_type"),
    )


def downgrade() -> None:
    op.drop_table("claim_events")
    op.drop_table("return_claims")
