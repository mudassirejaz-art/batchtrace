"""Add immutable CSV inventory observations; does not alter existing tables.

Revision ID: a7e65ca94f10
Revises: 2cc9cbd12023
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a7e65ca94f10"
down_revision: Union[str, Sequence[str], None] = "2cc9cbd12023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("original_file_sha256", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("row_count > 0", name="ck_import_row_count_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "observed_on", "content_sha256", name="uq_import_org_day_content"),
    )
    op.create_table(
        "inventory_snapshot_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("observed_quantity >= 0", name="ck_snapshot_nonnegative"),
        sa.ForeignKeyConstraint(["import_id"], ["inventory_imports.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_id", "lot_id", name="uq_import_lot_once"),
    )


def downgrade() -> None:
    op.drop_table("inventory_snapshot_rows")
    op.drop_table("inventory_imports")
