"""BotEvent model — universal analytics log for every user interaction."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.database import Base


class BotEvent(Base):
    """Every meaningful user action is logged here for analytics.

    event_type examples:
        menu_tap        — user tapped a reply-keyboard button
        command         — user issued a /command
        callback        — user pressed an inline-keyboard button
        premium_click   — user tapped 'Премиум'
        feedback_start  — user tapped 'Обратная связь'
        feedback_rating — user submitted a 1-5 rating
        feedback_text   — user submitted free-text feedback
        log_start       — symptom diary session started
        log_complete    — symptom diary session completed (with triage result)
        report_generated— PDF report generated
        onboarding_done — user completed /start onboarding
        patient_added   — new patient profile created
        patient_switched— active patient changed
        condition_changed— nosology/complaint updated
    """

    __tablename__ = "bot_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(BigInteger, index=True)

    event_type: Mapped[str] = mapped_column(String(50), index=True)

    # Optional structured payload (e.g. {"nosology": "ars", "triage_level": "green"})
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)

    # Optional human-readable detail (e.g. button text, command name)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<BotEvent(id={self.id}, user_id={self.user_id}, "
            f"event_type={self.event_type})>"
        )
