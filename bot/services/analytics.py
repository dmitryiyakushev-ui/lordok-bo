"""Lightweight analytics helper — fire-and-forget event logging."""

import logging
from typing import Any

from bot.db.database import get_session
from bot.models.event import BotEvent

logger = logging.getLogger(__name__)


async def log_event(
    user_id: int,
    event_type: str,
    detail: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Persist a BotEvent row. Never raises — failures are logged and swallowed."""
    try:
        async with get_session() as session:
            session.add(BotEvent(
                user_id=user_id,
                event_type=event_type,
                detail=detail,
                payload=payload,
            ))
    except Exception:
        logger.warning(
            "Failed to log event %s for user %s", event_type, user_id,
            exc_info=True,
        )
