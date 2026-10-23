"""Add PostgreSQL-backed login throttling counters (no existing table changes).

Revision ID: e7b54d260a91
Revises: d6f20a718c43
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e7b54d260a91"
down_revision: Union[str, Sequence[str], None] = "d6f20a718c43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_login_rate_limits",
        sa.Column("throttle_key", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("throttle_key"),
        sa.CheckConstraint("attempt_count > 0", name="ck_auth_rate_count_positive"),
    )


def downgrade() -> None:
    op.drop_table("auth_login_rate_limits")
