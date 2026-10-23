from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey,
    ForeignKeyConstraint, Integer, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReturnPolicyVersion(Base):
    __tablename__ = "return_policy_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
            name="fk_policy_org_supplier",
        ),
        UniqueConstraint(
            "organization_id", "supplier_id", "version",
            name="uq_policy_supplier_version",
        ),
        CheckConstraint(
            "version > 0", name="ck_policy_version_positive"
        ),
        CheckConstraint(
            "days_before_expiry BETWEEN 0 AND 3650",
            name="ck_policy_before_range",
        ),
        CheckConstraint(
            "days_after_expiry BETWEEN 0 AND 3650",
            name="ck_policy_after_range",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_policy_effective_range",
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
    supplier_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    days_before_expiry: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    days_after_expiry: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    effective_from: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    effective_to: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    created_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
