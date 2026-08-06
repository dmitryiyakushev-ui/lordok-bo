"""Scheduled messages: daily reminders, reactivation nudges, weekly digest.

Three jobs live here:

1. Per-user daily reminder at the time chosen during onboarding.
   Skipped when the diary is already filled today or the case is closed.
2. Daily reactivation sweep: users silent for exactly 3, 7 or 14 local
   days get one nudge each.
3. Weekly digest on Sunday evening for users who logged anything
   during the week.
"""

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from bot.config import get_settings
from bot.db.database import get_session
from bot.models.patient import Patient
from bot.models.symptom import SymptomEntry
from bot.models.user import User
from bot.services.analytics import log_event

logger = logging.getLogger(__name__)

DEFAULT_TZ = "Europe/Moscow"

# Days of silence that trigger a reactivation nudge.
REACTIVATION_DAYS = (3, 7, 14)

REACTIVATION_TEXTS = {
    3: (
        "Три дня без записей. Пара минут сейчас, и динамика не потеряется."
    ),
    7: (
        "Неделя без записей. Если стало легче, отметьте это: врачу важно "
        "видеть, что симптомы ушли, а не просто пропали из дневника."
    ),
    14: (
        "Две недели тишины. Продолжаем вести дневник или случай можно "
        "закрыть? Закрыть можно в разделе «Пациенты»."
    ),
}


def _as_utc(value: datetime) -> datetime:
    """Treat naive timestamps as UTC (legacy rows written before tz-aware)."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _safe_tz(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TZ)
    except Exception:
        logger.warning("Invalid timezone %r, falling back to %s", tz_name, DEFAULT_TZ)
        return ZoneInfo(DEFAULT_TZ)


def _local_day_start_utc(
    tz_name: str | None,
    now_utc: datetime | None = None,
    days_back: int = 0,
) -> datetime:
    """Start of the user's local day (shifted back by days_back), in UTC."""
    now_utc = now_utc or datetime.now(timezone.utc)
    tz = _safe_tz(tz_name)
    local = now_utc.astimezone(tz)
    day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_start -= timedelta(days=days_back)
    return day_start.astimezone(timezone.utc)


def _log_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Заполнить дневник", callback_data="start_log")],
        ]
    )


class ReminderScheduler:
    """Manages daily reminder scheduling for users."""

    def __init__(self):
        settings = get_settings()
        self.tz = ZoneInfo(settings.timezone)  # Europe/Moscow by default
        self.scheduler = AsyncIOScheduler(timezone=self.tz)
        self.bot: Bot = None

    async def start(self, bot: Bot):
        """Initialize scheduler and load existing user reminders."""
        self.bot = bot
        self.scheduler.start()

        await self._schedule_all_users()
        self._schedule_service_jobs()
        logger.info("Reminder scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Reminder scheduler stopped")

    async def _schedule_all_users(self):
        """Load all users and schedule their reminders."""
        async with get_session() as session:
            stmt = select(User)
            result = await session.execute(stmt)
            users = result.scalars().all()

        for user in users:
            await self._schedule_user_reminder(user)

    def _schedule_service_jobs(self):
        """Register the two account-wide jobs (reactivation, weekly digest)."""
        self.scheduler.add_job(
            self._reactivation_sweep,
            "cron",
            hour=12,
            minute=0,
            timezone=self.tz,
            id="reactivation_sweep",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._weekly_digest,
            "cron",
            day_of_week="sun",
            hour=18,
            minute=0,
            timezone=self.tz,
            id="weekly_digest",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info("Service jobs scheduled: reactivation sweep, weekly digest")

    async def _schedule_user_reminder(self, user: User):
        """Schedule a daily reminder for a specific user."""
        if not user.reminder_time:
            return
        if user.blocked_at is not None:
            return

        # reminder_time is a Python time object from SQLAlchemy
        if isinstance(user.reminder_time, str):
            try:
                hour, minute = map(int, user.reminder_time.split(":"))
            except ValueError:
                logger.error(f"Invalid reminder_time format for user {user.id}: {user.reminder_time}")
                return
        else:
            hour = user.reminder_time.hour
            minute = user.reminder_time.minute

        # Use per-user timezone, fall back to global
        user_tz_name = getattr(user, "user_tz", None) or DEFAULT_TZ
        user_tz = _safe_tz(user_tz_name)

        job_id = f"reminder_{user.id}"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            self._send_reminder,
            "cron",
            hour=hour,
            minute=minute,
            timezone=user_tz,
            args=[user.id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=3600,  # send even if up to 1h late (e.g. after restart)
        )

        logger.debug(f"Scheduled reminder for user {user.id} at {hour:02d}:{minute:02d} ({user_tz_name})")

    async def _send(self, user_id: int, text: str, keyboard=None) -> bool:
        """Отправить сообщение и запомнить, если бота заблокировали."""
        try:
            await self.bot.send_message(
                chat_id=user_id, text=text, reply_markup=keyboard
            )
            return True
        except TelegramForbiddenError:
            logger.info("User %s blocked the bot, plans cancelled", user_id)
            await self._mark_blocked(user_id)
        except Exception as e:
            logger.error("Failed to send message to user %s: %s", user_id, e)
        return False

    async def _mark_blocked(self, user_id: int) -> None:
        """Пометить блокировку и снять запланированное напоминание."""
        async with get_session() as session:
            user = await session.get(User, user_id)
            if user is not None and user.blocked_at is None:
                user.blocked_at = datetime.now(timezone.utc)

        job_id = f"reminder_{user_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    async def _send_reminder(self, user_id: int):
        """Send the daily reminder unless it would be pointless.

        Skipped when the active patient's case is closed or the diary
        has already been filled today in the user's own timezone.
        """
        async with get_session() as session:
            user = await session.get(User, user_id)
            if user is None:
                return
            if not user.active_patient_id:
                return

            patient = await session.get(Patient, user.active_patient_id)
            if patient is None or patient.case_closed_at is not None:
                logger.debug(
                    "Skipping reminder for user %s: case closed or no patient",
                    user_id,
                )
                return

            day_start = _local_day_start_utc(user.user_tz)
            already_logged = (
                await session.execute(
                    select(func.count())
                    .select_from(SymptomEntry)
                    .where(SymptomEntry.patient_id == patient.id)
                    .where(SymptomEntry.recorded_at >= day_start)
                )
            ).scalar() or 0

        if already_logged:
            logger.debug("Skipping reminder for user %s: already logged today", user_id)
            return

        await self._send(user_id, "⏰ Время записать симптомы 📝", _log_keyboard())

    async def _reactivation_sweep(self):
        """Nudge users who went silent for exactly 3, 7 or 14 local days."""
        now_utc = datetime.now(timezone.utc)
        sent = 0

        async with get_session() as session:
            last_entry = (
                select(
                    SymptomEntry.patient_id.label("patient_id"),
                    func.max(SymptomEntry.recorded_at).label("last_at"),
                )
                .group_by(SymptomEntry.patient_id)
                .subquery()
            )
            rows = (
                await session.execute(
                    select(User, last_entry.c.last_at)
                    .join(Patient, Patient.id == User.active_patient_id)
                    .join(last_entry, last_entry.c.patient_id == Patient.id)
                    .where(Patient.case_closed_at.is_(None))
                    .where(User.blocked_at.is_(None))
                )
            ).all()

        for user, last_at in rows:
            if last_at is None:
                continue

            today_start = _local_day_start_utc(user.user_tz, now_utc)
            days_silent = (today_start - _local_day_start_utc(
                user.user_tz, _as_utc(last_at)
            )).days

            if days_silent not in REACTIVATION_DAYS:
                continue

            ok = await self._send(
                user.id, REACTIVATION_TEXTS[days_silent], _log_keyboard()
            )
            if ok:
                sent += 1
                await log_event(
                    user_id=user.id,
                    event_type="reactivation_sent",
                    detail=str(days_silent),
                )

        logger.info("Reactivation sweep: %d nudge(s) sent", sent)

    async def _weekly_digest(self):
        """Sunday evening summary for users who logged during the week."""
        messages: list[tuple[int, str]] = []

        async with get_session() as session:
            rows = (
                await session.execute(
                    select(User, Patient)
                    .join(Patient, Patient.id == User.active_patient_id)
                    .where(Patient.case_closed_at.is_(None))
                    .where(User.blocked_at.is_(None))
                )
            ).all()

            for user, patient in rows:
                week_start = _local_day_start_utc(user.user_tz, days_back=6)

                entries = (
                    await session.execute(
                        select(SymptomEntry.recorded_at, SymptomEntry.triage_level)
                        .where(SymptomEntry.patient_id == patient.id)
                        .where(SymptomEntry.recorded_at >= week_start)
                    )
                ).all()

                if not entries:
                    continue

                tz = _safe_tz(user.user_tz)
                days = {_as_utc(rec).astimezone(tz).date() for rec, _ in entries}
                levels = [level for _, level in entries]
                green = levels.count("green")
                yellow = levels.count("yellow")
                red = levels.count("red")

                text = (
                    f"📅 Итоги недели — {patient.display_name}\n\n"
                    f"Заполнено дней: {len(days)} из 7\n"
                    f"Оценки: 🟢 {green} · 🟡 {yellow} · 🔴 {red}\n\n"
                )
                if red:
                    text += (
                        "На неделе были красные оценки. Если к врачу так и не "
                        "сходили, самое время."
                    )
                elif len(days) >= 5:
                    text += (
                        "Хорошая неделя по регулярности. Отчёт для врача можно "
                        "собрать в разделе «Отчёт»."
                    )
                else:
                    text += (
                        "Чем меньше пропусков, тем понятнее динамика на приёме."
                    )

                messages.append((user.id, text))

        sent = 0
        for user_id, text in messages:
            if await self._send(user_id, text):
                sent += 1

        logger.info("Weekly digest: %d message(s) sent", sent)

    async def update_user_reminder(self, user: User):
        """Re-schedule reminder when user updates their settings."""
        await self._schedule_user_reminder(user)
