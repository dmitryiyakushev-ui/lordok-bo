"""Funnel metrics: activation, retention, North Star, source breakdown.

Definitions used here (they are the ones the MVP is judged by):

- Старт          — событие `start` в bot_events, уникальные пользователи.
- Регистрация    — событие `onboarding_done`.
- Активация      — 3 и более дней с записями в первые 7 дней после
                   регистрации. Считается только по тем, кто
                   зарегистрировался не позже чем 7 дней назад.
- Retention D_N  — доля пользователей, у которых есть запись ровно на
                   N-й день от даты регистрации. Знаменатель — те, кто
                   успел дожить до этого дня.
- North Star     — 5 и более дней с записями в каждой из последних
                   4 недель подряд.

Дни считаются по UTC, а не по часовому поясу пользователя: для сводных
метрик сдвиг в пару часов не меняет решения, а код остаётся простым.
"""

from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.event import BotEvent
from bot.models.symptom import SymptomEntry
from bot.models.user import User

from bot.services.funnel_math import (
    RETENTION_DAYS,
    compute_activation,
    compute_north_star,
    compute_retention,
)


async def _entry_days_by_user(session: AsyncSession) -> dict[int, set[date]]:
    """user_id -> set of UTC dates that have at least one diary entry."""
    rows = (
        await session.execute(
            select(SymptomEntry.user_id, cast(SymptomEntry.recorded_at, Date))
            .distinct()
        )
    ).all()

    days: dict[int, set[date]] = defaultdict(set)
    for user_id, day in rows:
        days[user_id].add(day)
    return days


async def collect_funnel(session: AsyncSession, now: datetime | None = None) -> dict:
    """Compute the funnel metrics over the whole user base."""
    now = now or datetime.now(timezone.utc)
    today = now.date()

    users = (
        await session.execute(select(User.id, User.created_at, User.source))
    ).all()
    entry_days = await _entry_days_by_user(session)

    starts = (
        await session.execute(
            select(func.count(func.distinct(BotEvent.user_id)))
            .where(BotEvent.event_type == "start")
        )
    ).scalar() or 0

    # События `start` пишутся только с версии, где появилась атрибуция.
    # Сравнивать их с полной базой пользователей нельзя, поэтому верх
    # воронки считаем от момента, когда счётчик включился.
    first_start_at = (
        await session.execute(
            select(func.min(BotEvent.created_at))
            .where(BotEvent.event_type == "start")
        )
    ).scalar()

    if first_start_at is None:
        registered = 0
    else:
        registered = sum(1 for _, created_at, _ in users if created_at >= first_start_at)

    signup_days = [(user_id, created_at.date()) for user_id, created_at, _ in users]

    activation = compute_activation(signup_days, entry_days, today)
    retention = {
        day_n: compute_retention(signup_days, entry_days, today, day_n)
        for day_n in RETENTION_DAYS
    }
    nsm = compute_north_star(entry_days, today)

    # ── Источники ──
    source_rows = (
        await session.execute(
            select(BotEvent.detail, func.count(func.distinct(BotEvent.user_id)))
            .where(BotEvent.event_type == "start")
            .group_by(BotEvent.detail)
            .order_by(func.count(func.distinct(BotEvent.user_id)).desc())
            .limit(10)
        )
    ).all()

    registered_by_source = (
        await session.execute(
            select(
                func.coalesce(User.source, "direct"),
                func.count(),
            ).group_by(func.coalesce(User.source, "direct"))
        )
    ).all()

    return {
        "starts": starts,
        "registered": registered,
        "counter_since": first_start_at,
        "activation": activation,
        "retention": retention,
        "nsm": nsm,
        "sources_started": [(s or "direct", c) for s, c in source_rows],
        "sources_registered": list(registered_by_source),
    }


def _pct(part: int, whole: int) -> str:
    if not whole:
        return "нет данных"
    return f"{part * 100 // whole}% ({part} из {whole})"


def format_funnel(data: dict) -> list[str]:
    """Render the funnel block for /stats."""
    activated, act_eligible = data["activation"]

    since = data.get("counter_since")
    since_note = f" (с {since:%d.%m.%Y})" if since else ""

    lines = [
        f"🔻 Воронка{since_note}:",
        f"  Стартов: {data['starts']}",
        f"  Дошли до конца регистрации: {_pct(data['registered'], data['starts'])}",
        f"  Активация (3+ дня за первую неделю): {_pct(activated, act_eligible)}",
        "",
        "📉 Retention:",
    ]

    for day_n in RETENTION_DAYS:
        returned, eligible = data["retention"].get(day_n, (0, 0))
        lines.append(f"  D{day_n}: {_pct(returned, eligible)}")

    lines += [
        "",
        f"⭐ North Star (5 дней в неделю 4 недели подряд): {data['nsm']}",
    ]

    if data["sources_started"]:
        lines += ["", "🔗 Источники (стартов / дошли до регистрации):"]
        registered_map = dict(data["sources_registered"])
        for source, started in data["sources_started"]:
            lines.append(
                f"  {source}: {started} / {registered_map.get(source, 0)}"
            )

    return lines
