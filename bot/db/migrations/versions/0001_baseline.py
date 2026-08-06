"""Базовая ревизия: текущая схема ЛОРдока.

Ревизия одинаково отрабатывает на трёх состояниях базы:

- пустая база: таблицы создаются по моделям;
- база, созданная старым create_all: недостающие колонки, внешние
  ключи и индексы добавляются, легаси-пользователи переносятся
  в таблицу пациентов;
- уже актуальная база: ничего не меняется.

Дальше схема живёт обычными ревизиями alembic.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-06
"""

from alembic import op

from bot.db.database import Base
from bot.db.legacy_schema import catch_up
import bot.models  # noqa: F401 — регистрирует таблицы в Base.metadata

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    Base.metadata.create_all(bind=conn, checkfirst=True)
    catch_up(conn)


def downgrade() -> None:
    raise NotImplementedError(
        "Базовая ревизия не откатывается: она сносила бы всю базу целиком."
    )
