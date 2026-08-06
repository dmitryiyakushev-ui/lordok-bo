"""Общая обвязка тестов: настройки окружения и база в памяти.

Тесты, которым нужна база, работают на SQLite через aiosqlite: схема
создаётся из моделей, миграции alembic здесь не участвуют. Это проверка
кода бота, а не диалекта Postgres.
"""

import os

import pytest

# Настройки читаются при импорте модулей бота, поэтому переменные
# окружения выставляются до любых импортов из bot.*
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("FSM_STORAGE", "memory")
os.environ.setdefault("TIMEZONE", "Europe/Moscow")

from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.db import database  # noqa: E402
import bot.models  # noqa: E402,F401 — регистрирует таблицы в метаданных


@pytest.fixture
async def db():
    """Пустая база в памяти на время одного теста."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async with engine.begin() as conn:
        await conn.run_sync(database.Base.metadata.create_all)

    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # get_session() смотрит на модульные переменные, подменяем их.
    previous_engine = database._engine
    previous_maker = database._async_session_maker
    database._engine = engine
    database._async_session_maker = session_maker

    try:
        yield session_maker
    finally:
        database._engine = previous_engine
        database._async_session_maker = previous_maker
        await engine.dispose()
