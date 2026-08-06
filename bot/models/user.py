"""User model — Telegram account that owns one or more Patient profiles."""

from datetime import datetime, time, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.database import Base


class User(Base):
    """Telegram account profile and settings.

    Medical data (nosology, age, sex, DoB) lives on Patient, not here.
    The `nosology`/`age_group` columns are retained as legacy-readable
    only for the one-time resolution flow and are never written to
    by new onboarding.
    """

    __tablename__ = "users"

    # Primary key — Telegram user_id
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Telegram user info
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255))
    language_code: Mapped[str] = mapped_column(String(10), default="ru")

    # Account-level profile (new)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Acquisition source — deep-link payload from the /start link
    # (t.me/<bot>?start=<source>). Written once, never overwritten.
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Consent to personal data processing (152-ФЗ). Health data is a
    # special category, so the acceptance itself has to be recorded:
    # which document version, and when.
    consent_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Active patient pointer — which patient /log, /history, /report work with
    active_patient_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Legacy fields (retained for migration; not written by new onboarding)
    nosology: Mapped[str | None] = mapped_column(String(50), nullable=True)
    age_group: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Preferences
    reminder_time: Mapped[time] = mapped_column(Time, default=time(20, 0))
    user_tz: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, username={self.username}, "
            f"full_name={self.full_name!r})>"
        )
