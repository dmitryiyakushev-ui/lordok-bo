import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from bot.config import get_settings
from bot.db.database import get_session
from bot.models.user import User

logger = logging.getLogger(__name__)


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

    async def _schedule_user_reminder(self, user: User):
        """Schedule a daily reminder for a specific user."""
        if not user.reminder_time:
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
        user_tz_name = getattr(user, "user_tz", None) or "Europe/Moscow"
        try:
            user_tz = ZoneInfo(user_tz_name)
        except (KeyError, Exception):
            logger.warning(f"Invalid timezone '{user_tz_name}' for user {user.id}, falling back to Europe/Moscow")
            user_tz = self.tz

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

    async def _send_reminder(self, user_id: int):
        """Send daily reminder message to user.

        Skips sending if the active patient's case is closed
        (case_closed_at is set).
        """
        try:
            # Check if active patient has a closed case — skip if so.
            from bot.models.patient import Patient
            async with get_session() as session:
                user = await session.get(User, user_id)
                if user and user.active_patient_id:
                    patient = await session.get(Patient, user.active_patient_id)
                    if patient and patient.case_closed_at is not None:
                        logger.debug(
                            f"Skipping reminder for user {user_id}: "
                            f"case closed for patient {patient.id}"
                        )
                        return

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="Заполнить дневник",
                        callback_data="start_log"
                    )],
                ]
            )

            await self.bot.send_message(
                chat_id=user_id,
                text="⏰ Время записать симптомы 📝",
                reply_markup=keyboard
            )
            logger.debug(f"Reminder sent to user {user_id}")

        except Exception as e:
            logger.error(f"Failed to send reminder to user {user_id}: {e}")

    async def update_user_reminder(self, user: User):
        """Re-schedule reminder when user updates their settings."""
        await self._schedule_user_reminder(user)
