"""Symptom entry model — diary entry with triage assessment."""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.database import Base


class SymptomEntry(Base):
    """Symptom diary entry for a specific Patient."""

    __tablename__ = "symptom_entries"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Owner account (retained for convenience; denormalized from Patient.user_id)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Primary link — the patient this entry belongs to.
    # Nullable during migration window; new code always writes a value.
    patient_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )

    # Denormalized medical context (for query speed)
    nosology: Mapped[str] = mapped_column(String(50), index=True)

    # Timestamp
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Symptom data
    symptoms: Mapped[dict] = mapped_column(JSON, default=dict)

    # Triage results
    composite_score: Mapped[int] = mapped_column(Integer, default=0)
    triage_level: Mapped[str] = mapped_column(String(20), default="green", index=True)
    triage_message: Mapped[str] = mapped_column(Text, default="")

    # Red flags
    red_flags: Mapped[list] = mapped_column(JSON, default=list)

    # Treatment context (for diagnosed patients)
    # last_doctor_visit: 0=<1wk, 1=1-2wk, 2=2-4wk, 3=>1mo, 4=never
    last_doctor_visit: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # treatment_status: "prescribed", "self", "none"
    treatment_status: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)

    # Free-text patient note ("Хотите что-то дополнить?")
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # Relationships
    user: Mapped["User"] = relationship("User")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<SymptomEntry(id={self.id}, user_id={self.user_id}, "
            f"patient_id={self.patient_id}, nosology={self.nosology}, "
            f"triage_level={self.triage_level})>"
        )
