"""Patient model — medical entity tracked by an account.

One Telegram account (User) may have multiple Patient records:
- relation='self'  — account owner as a patient
- relation='child' — a child being monitored by the account owner

Source distinguishes user-added records from legacy-migrated ones that
still require resolution (e.g., is this data about the user or a child?).
"""

from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Owner account
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Who this patient is relative to the account
    relation: Mapped[str] = mapped_column(
        String(10),
        default="self",
        comment="'self' | 'child'",
    )

    # Where the record came from
    source: Mapped[str] = mapped_column(
        String(20),
        default="user_added",
        comment="'user_added' | 'legacy_migration'",
    )

    # True for legacy records awaiting user clarification (self vs child)
    needs_resolution: Mapped[bool] = mapped_column(Boolean, default=False)

    # Display name (independent from users.full_name)
    display_name: Mapped[str] = mapped_column(String(255))

    # Demographics
    sex: Mapped[str | None] = mapped_column(
        String(1),
        nullable=True,
        comment="'m' | 'f' | None",
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Legacy age bucket — only for migrated records until DoB is resolved.
    # New records must always derive age_group from date_of_birth.
    legacy_age_group: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Transitional attribute for legacy records only",
    )

    # Medical context
    nosology: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="ars, crs, tonsillopharyngitis, aom, com, adenoid_hypertrophy, undiagnosed_*",
    )

    # Case lifecycle: when set, the current episode is considered closed.
    # Next diary fill will be treated as a new case (asks duration, etc.)
    # and the field is reset to None automatically.
    case_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Set when patient closes current case; cleared on next diary fill",
    )

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

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
            f"<Patient(id={self.id}, user_id={self.user_id}, "
            f"relation={self.relation}, name={self.display_name!r}, "
            f"nosology={self.nosology})>"
        )
