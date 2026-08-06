"""Feedback model — user ratings and comments about the bot."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.database import Base


class Feedback(Base):
    """User satisfaction feedback collected via the menu button."""

    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # 1–5 rating
    rating: Mapped[int] = mapped_column(SmallInteger)

    # Free-text comment (may be None if user skipped)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Feedback(id={self.id}, user_id={self.user_id}, "
            f"rating={self.rating})>"
        )
