"""Immutable imports and their observed quantities. No live stock mutation."""
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Integer,
    String, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryImport(Base):
    __tablename__ = "inventory_imports"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "observed_on", "content_sha256",
            name="uq_import_org_day_content",
        ),
        CheckConstraint("row_count > 0", name="ck_import_row_count_positive"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InventorySnapshotRow(Base):
    __tablename__ = "inventory_snapshot_rows"
    __table_args__ = (
        UniqueConstraint("import_id", "lot_id", name="uq_import_lot_once"),
        CheckConstraint("observed_quantity >= 0", name="ck_snapshot_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    import_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("inventory_imports.id", ondelete="RESTRICT"), nullable=False,
    )
    lot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observed_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
