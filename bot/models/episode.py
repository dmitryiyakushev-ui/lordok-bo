"""EpisodeLog model — tracks discrete clinical episodes (tonsillitis, AOM, CRS flare)."""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.database import Base


class EpisodeLog(Base):
    """Records a discrete clinical episode for episode-counting criteria."""

    __tablename__ = "episode_logs"

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

    # Episode type: "tonsillitis", "aom", "crs_flare"
    episode_type: Mapped[str] = mapped_column(String(32), index=True)

    # Whether a doctor confirmed the episode (patient can update later)
    confirmed_by_doctor: Mapped[bool] = mapped_column(Boolean, default=False)

    # Associated scale score at episode start (e.g. Centor score)
    scale_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Episode timeline
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Free-text notes (e.g. "antibiotics prescribed", "RADT positive")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<EpisodeLog(id={self.id}, user_id={self.user_id}, "
            f"episode_type={self.episode_type}, started_at={self.started_at})>"
        )
