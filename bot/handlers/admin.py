"""Admin-only handlers: /stats and diagnostic tools.

Access is restricted to user IDs listed in ADMIN_IDS env var.
"""

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select, text

from bot.config import get_settings
from bot.db.database import get_session
from bot.models.event import BotEvent
from bot.models.feedback import Feedback
from bot.models.patient import Patient
from bot.models.symptom import SymptomEntry
from bot.models.user import User
from bot.services.metrics import collect_funnel, format_funnel

logger = logging.getLogger(__name__)
router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not _is_admin(message.from_user.id):
        return  # silently ignore for non-admins

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    async with get_session() as session:
        # --- Users ---
        total_users = (await session.execute(
            select(func.count()).select_from(User)
        )).scalar() or 0

        users_7d = (await session.execute(
            select(func.count()).select_from(User).where(User.created_at >= week_ago)
        )).scalar() or 0

        # --- Patients ---
        total_patients = (await session.execute(
            select(func.count()).select_from(Patient)
        )).scalar() or 0

        # --- Diary entries ---
        total_entries = (await session.execute(
            select(func.count()).select_from(SymptomEntry)
        )).scalar() or 0

        entries_24h = (await session.execute(
            select(func.count()).select_from(SymptomEntry)
            .where(SymptomEntry.recorded_at >= day_ago)
        )).scalar() or 0

        entries_7d = (await session.execute(
            select(func.count()).select_from(SymptomEntry)
            .where(SymptomEntry.recorded_at >= week_ago)
        )).scalar() or 0

        entries_30d = (await session.execute(
            select(func.count()).select_from(SymptomEntry)
            .where(SymptomEntry.recorded_at >= month_ago)
        )).scalar() or 0

        # --- Active users (logged at least 1 entry) ---
        active_7d = (await session.execute(
            select(func.count(func.distinct(SymptomEntry.user_id)))
            .where(SymptomEntry.recorded_at >= week_ago)
        )).scalar() or 0

        active_30d = (await session.execute(
            select(func.count(func.distinct(SymptomEntry.user_id)))
            .where(SymptomEntry.recorded_at >= month_ago)
        )).scalar() or 0

        # --- Triage distribution (last 30 days) ---
        triage_rows = (await session.execute(
            select(SymptomEntry.triage_level, func.count())
            .where(SymptomEntry.recorded_at >= month_ago)
            .group_by(SymptomEntry.triage_level)
        )).all()
        triage_dist = {row[0]: row[1] for row in triage_rows}

        # --- Feedback ---
        total_feedback = (await session.execute(
            select(func.count()).select_from(Feedback)
        )).scalar() or 0

        funnel = await collect_funnel(session, now)

        avg_rating = (await session.execute(
            select(func.avg(Feedback.rating))
        )).scalar()

        recent_feedback = (await session.execute(
            select(Feedback.rating, Feedback.comment, Feedback.created_at)
            .order_by(Feedback.created_at.desc())
            .limit(5)
        )).all()

        # --- Top nosologies (last 30 days) ---
        noso_rows = (await session.execute(
            select(SymptomEntry.nosology, func.count())
            .where(SymptomEntry.recorded_at >= month_ago)
            .group_by(SymptomEntry.nosology)
            .order_by(func.count().desc())
            .limit(5)
        )).all()

    # Format
    green = triage_dist.get("green", 0)
    yellow = triage_dist.get("yellow", 0)
    red = triage_dist.get("red", 0)
    triage_total = green + yellow + red

    lines = [
        "📊 Статистика ЛОРдок",
        "",
        f"👥 Пользователей: {total_users} (новых за 7д: {users_7d})",
        f"🧑‍⚕️ Пациентов: {total_patients}",
        "",
        "📝 Записи в дневнике:",
        f"  Всего: {total_entries}",
        f"  24ч: {entries_24h} | 7д: {entries_7d} | 30д: {entries_30d}",
        "",
        f"📈 Активные пользователи: 7д: {active_7d} | 30д: {active_30d}",
        "",
        "🚦 Триаж за 30д:",
    ]

    if triage_total:
        lines.append(
            f"  🟢 {green} ({green*100//triage_total}%) "
            f"| 🟡 {yellow} ({yellow*100//triage_total}%) "
            f"| 🔴 {red} ({red*100//triage_total}%)"
        )
    else:
        lines.append("  Нет данных")

    if noso_rows:
        lines.append("")
        lines.append("🏥 Топ нозологий (30д):")
        for noso, cnt in noso_rows:
            lines.append(f"  {noso}: {cnt}")

    lines.append("")
    lines.extend(format_funnel(funnel))

    lines.append("")
    lines.append(
        f"💬 Отзывов: {total_feedback}"
        + (f" | Средняя оценка: {avg_rating:.1f}/5" if avg_rating else "")
    )

    if recent_feedback:
        lines.append("")
        lines.append("Последние отзывы:")
        for rating, comment, created_at in recent_feedback:
            stars = "⭐" * rating
            date_str = created_at.strftime("%d.%m")
            text_preview = ""
            if comment:
                text_preview = f': "{comment[:60]}{"…" if len(comment) > 60 else ""}"'
            lines.append(f"  {date_str} {stars}{text_preview}")

    await message.answer("\n".join(lines))
