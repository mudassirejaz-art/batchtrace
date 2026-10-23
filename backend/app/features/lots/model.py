from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import (
    Date, DateTime, ForeignKey, ForeignKeyConstraint,
    String, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Lot(Base):
    __tablename__ = "lots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
            name="fk_lot_org_product",
        ),
        ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
            name="fk_lot_org_supplier",
        ),
        UniqueConstraint(
            "organization_id", "product_id",
            "supplier_id", "batch_number", "expiry_date",
            name="uq_lot_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    supplier_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    batch_number: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
