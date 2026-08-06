"""Main entry point for ЛОРдок bot."""

import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, Update
from aiohttp_socks import ProxyConnector
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import get_settings
from bot.db.database import init_db, close_db
from bot.services.scheduler import ReminderScheduler


# Configure logging
def _setup_logging() -> None:
    """Configure logging based on settings."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# Global instances
_bot: Optional[Bot] = None
_dp: Optional[Dispatcher] = None
_scheduler: Optional[AsyncIOScheduler] = None
_reminder_scheduler: Optional[ReminderScheduler] = None


def get_bot() -> Bot:
    """Get bot instance."""
    if _bot is None:
        raise RuntimeError("Bot not initialized. Call setup_bot() first.")
    return _bot


def get_dispatcher() -> Dispatcher:
    """Get dispatcher instance."""
    if _dp is None:
        raise RuntimeError("Dispatcher not initialized. Call setup_bot() first.")
    return _dp


def get_scheduler() -> AsyncIOScheduler:
    """Get scheduler instance."""
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call setup_bot() first.")
    return _scheduler


def get_reminder_scheduler() -> ReminderScheduler:
    """Get the ReminderScheduler instance (manages per-user daily reminders)."""
    if _reminder_scheduler is None:
        raise RuntimeError("ReminderScheduler not initialized.")
    return _reminder_scheduler


class ProxiedAiohttpSession(AiohttpSession):
    """AiohttpSession that routes traffic through a SOCKS5 proxy with remote DNS."""

    def __init__(self, proxy_url: str, **kwargs):
        super().__init__(**kwargs)
        self._proxy_url = proxy_url
        self._proxy_connector: Optional[ProxyConnector] = None

    async def create_session(self) -> "ClientSession":
        from aiohttp import ClientSession

        if self._session is None or self._session.closed:
            self._proxy_connector = ProxyConnector.from_url(
                self._proxy_url, rdns=True
            )
            self._session = ClientSession(connector=self._proxy_connector)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        await super().close()


def _build_storage() -> BaseStorage:
    """Build the FSM storage.

    Redis by default: a container restart must not drop users in the
    middle of onboarding or a diary session. MemoryStorage stays
    available for local debugging without Redis (FSM_STORAGE=memory).
    """
    settings = get_settings()
    logger = logging.getLogger(__name__)

    if settings.fsm_storage.lower() == "memory":
        logger.warning(
            "FSM storage: memory, dialog state is lost on restart. "
            "Use FSM_STORAGE=redis in production."
        )
        return MemoryStorage()

    logger.info("FSM storage: redis")
    return RedisStorage.from_url(settings.redis_url)


async def setup_bot() -> tuple[Bot, Dispatcher, AsyncIOScheduler]:
    """Setup bot, dispatcher, and scheduler."""
    global _bot, _dp, _scheduler

    settings = get_settings()
    logger = logging.getLogger(__name__)

    # Initialize bot and dispatcher (with optional SOCKS proxy for Telegram API)
    session = None
    if settings.https_proxy:
        session = ProxiedAiohttpSession(proxy_url=settings.https_proxy)
        logger.info("Using proxy: %s (rdns=True)", settings.https_proxy)
    _bot = Bot(token=settings.bot_token, session=session)
    _dp = Dispatcher(storage=_build_storage())

    # Initialize scheduler
    _scheduler = AsyncIOScheduler()

    logger.info("Bot, dispatcher, and scheduler initialized")

    return _bot, _dp, _scheduler


BOT_COMMANDS = [
    BotCommand(command="log", description="📝 Дневник симптомов"),
    BotCommand(command="history", description="📋 История"),
    BotCommand(command="report", description="📊 PDF-отчёт"),
    BotCommand(command="patients", description="👥 Пациенты"),
    BotCommand(command="settings", description="⚙️ Настройки"),
    BotCommand(command="change_condition", description="Изменить жалобу/диагноз"),
    BotCommand(command="cancel", description="Отменить текущее действие"),
    BotCommand(command="help", description="Справка"),
    BotCommand(command="privacy", description="🔒 Мои данные и согласие"),
    BotCommand(command="my_data", description="Выгрузить мои данные"),
    BotCommand(command="delete_me", description="Удалить данные и отозвать согласие"),
    BotCommand(command="reset", description="Пересоздать профиль"),
]


async def on_startup() -> None:
    """Called on bot startup."""
    logger = logging.getLogger(__name__)
    logger.info("Starting up...")

    try:
        await init_db()
        logger.info("Database initialized")

        # Register native Telegram command menu (hamburger button in chat).
        try:
            bot = get_bot()
            await bot.set_my_commands(BOT_COMMANDS)
            logger.info("Bot commands registered in Telegram menu")
        except Exception as e:
            # Non-fatal: failing to set the command menu shouldn't block startup.
            logger.warning(f"Could not set bot commands: {e}")

        scheduler = get_scheduler()
        scheduler.start()
        logger.info("APScheduler started")

        # Start the reminder scheduler — loads per-user reminder jobs from DB.
        global _reminder_scheduler
        _reminder_scheduler = ReminderScheduler()
        bot = get_bot()
        await _reminder_scheduler.start(bot)
        logger.info("ReminderScheduler started, user reminders loaded")

    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise


async def on_shutdown() -> None:
    """Called on bot shutdown."""
    logger = logging.getLogger(__name__)
    logger.info("Shutting down...")

    try:
        # Stop reminder scheduler first (it has its own APScheduler instance).
        if _reminder_scheduler is not None:
            await _reminder_scheduler.stop()
            logger.info("ReminderScheduler stopped")

        scheduler = get_scheduler()
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler stopped")

        await close_db()
        logger.info("Database connection closed")

        if _dp is not None:
            await _dp.storage.close()
            logger.info("FSM storage closed")

        bot = get_bot()
        await bot.session.close()
        logger.info("Bot session closed")

    except Exception as e:
        logger.error(f"Shutdown error: {e}")
        raise


async def main() -> None:
    """Main entry point."""
    _setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Setup bot and dispatcher
        bot, dp, scheduler = await setup_bot()

        # Register startup and shutdown callbacks
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        # Register routers from handlers.
        # NB: menu_router MUST be included FIRST so that taps on the
        # persistent ReplyKeyboard main menu are caught before any
        # FSM-specific routers try to consume the message.
        from bot.handlers.menu import router as menu_router
        from bot.handlers.feedback import router as feedback_router
        from bot.handlers.admin import router as admin_router
        from bot.handlers.privacy import router as privacy_router
        from bot.handlers.start import router as start_router
        from bot.handlers.log import router as log_router
        from bot.handlers.history import router as history_router
        from bot.handlers.report import router as report_router
        from bot.handlers.common import router as common_router
        from bot.handlers.patients import router as patients_router

        dp.include_router(menu_router)
        dp.include_router(admin_router)     # before FSM routers
        dp.include_router(feedback_router)  # before FSM routers
        dp.include_router(privacy_router)   # before FSM routers
        dp.include_router(start_router)
        dp.include_router(log_router)
        dp.include_router(patients_router)
        dp.include_router(history_router)
        dp.include_router(report_router)
        dp.include_router(common_router)
        logger.info("All handler routers registered")

        logger.info("Starting polling...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
