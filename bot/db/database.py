"""Database initialization and session management."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

from bot.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Module-level engine and session factory
_engine = None
_async_session_maker = None


def _run_migrations(connection) -> None:
    """Прогнать alembic на уже открытом соединении."""
    from alembic import command
    from alembic.config import Config

    ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """Initialize database connection and bring the schema up to date."""
    global _engine, _async_session_maker

    settings = get_settings()
    _engine = create_async_engine(
        settings.database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

    _async_session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Схема живёт в alembic: одна точка правды вместо create_all плюс
    # самописных ALTER TABLE при старте.
    async with _engine.begin() as conn:
        await conn.run_sync(_run_migrations)


async def close_db() -> None:
    """Close database connection."""
    global _engine

    if _engine is not None:
        await _engine.dispose()
        _engine = None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session context manager."""
    if _async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
