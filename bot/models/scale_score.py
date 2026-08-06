"""ScaleScore model — validated clinical scale results (Centor, FeverPAIN, SNOT-22, etc.)."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.database import Base


class ScaleScore(Base):
    """Stores a validated clinical scale result for a patient."""

    __tablename__ = "scale_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    patient_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )

    # Scale identifier: "centor", "feverpain", "snot22", "stopbang"
    scale: Mapped[str] = mapped_column(String(16), index=True)

    # Computed score
    score: Mapped[int] = mapped_column(Integer)

    # Full item-level breakdown (for audit and delta analysis)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    # Clinical action derived from score (e.g. "green_no_ab", "yellow_test")
    action: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<ScaleScore(id={self.id}, user_id={self.user_id}, "
            f"scale={self.scale}, score={self.score})>"
        )
