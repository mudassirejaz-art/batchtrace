"""Persisted, non-identifying fixed-window authentication throttling counters."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuthLoginRateLimit(Base):
    __tablename__ = "auth_login_rate_limits"
    __table_args__ = (
        CheckConstraint("attempt_count > 0", name="ck_auth_rate_count_positive"),
    )

    throttle_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
