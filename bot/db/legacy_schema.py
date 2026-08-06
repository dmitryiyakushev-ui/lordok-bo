"""Догоняющие правки схемы для баз, созданных до alembic.

До августа 2026 схема жила на `Base.metadata.create_all()` плюс
самописные ALTER TABLE при старте бота. create_all не трогает уже
существующие таблицы, поэтому старой базе не хватает колонок, которые
появились позже.

Этот модуль приводит такую базу к текущему виду и делает разовый
перенос легаси-пользователей в таблицу пациентов. Вызывается один раз,
из первой ревизии alembic. Новые изменения схемы сюда не дописываются:
для них заводится обычная ревизия.

Все шаги идемпотентны, повторный запуск безопасен.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = :table AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    )
    return result.first() is not None


def _add_column_if_missing(conn: Connection, table: str, column: str, ddl: str) -> None:
    if not _column_exists(conn, table, column):
        logger.info("Adding column %s.%s", table, column)
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _add_fk_if_missing(
    conn: Connection, table: str, constraint_name: str, ddl: str
) -> None:
    result = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_name = :table AND constraint_name = :name
            """
        ),
        {"table": table, "name": constraint_name},
    )
    if result.first() is None:
        logger.info("Adding FK %s on %s", constraint_name, table)
        conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} {ddl}"))


def catch_up(conn: Connection) -> None:
    """Довести старую схему до текущей и перенести легаси-данные."""
    # ── users: аккаунт и профиль ──
    _add_column_if_missing(conn, "users", "full_name", "VARCHAR(255)")
    _add_column_if_missing(conn, "users", "phone", "VARCHAR(32)")
    _add_column_if_missing(conn, "users", "active_patient_id", "INTEGER")
    _add_fk_if_missing(
        conn,
        "users",
        "users_active_patient_id_fkey",
        "FOREIGN KEY (active_patient_id) REFERENCES patients(id) ON DELETE SET NULL",
    )
    _add_column_if_missing(conn, "users", "user_tz", "VARCHAR(50) DEFAULT 'Europe/Moscow'")
    _add_column_if_missing(conn, "users", "source", "VARCHAR(64)")
    _add_column_if_missing(conn, "users", "consent_version", "VARCHAR(16)")
    _add_column_if_missing(conn, "users", "consent_at", "TIMESTAMPTZ")

    # ── symptom_entries: привязка к пациенту и контекст лечения ──
    _add_column_if_missing(conn, "symptom_entries", "patient_id", "INTEGER")
    _add_fk_if_missing(
        conn,
        "symptom_entries",
        "symptom_entries_patient_id_fkey",
        "FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE",
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_symptom_entries_patient_id "
            "ON symptom_entries (patient_id)"
        )
    )
    _add_column_if_missing(conn, "symptom_entries", "user_notes", "TEXT")
    _add_column_if_missing(conn, "symptom_entries", "last_doctor_visit", "INTEGER")
    _add_column_if_missing(conn, "symptom_entries", "treatment_status", "VARCHAR(20)")

    # ── patients: закрытие случая ──
    _add_column_if_missing(conn, "patients", "case_closed_at", "TIMESTAMPTZ")

    # ── Разовый перенос легаси-пользователей ──
    # Легаси-пользователь: нозология проставлена, а карточки пациента нет.
    now = datetime.now(timezone.utc)

    legacy_users = conn.execute(
        text(
            """
            SELECT u.id, u.first_name, u.nosology, u.age_group
            FROM users u
            LEFT JOIN patients p ON p.user_id = u.id
            WHERE u.nosology IS NOT NULL AND p.id IS NULL
            """
        )
    ).fetchall()

    if legacy_users:
        logger.info("Backfilling %d legacy user(s) into patients", len(legacy_users))

    for row in legacy_users:
        patient_id = conn.execute(
            text(
                """
                INSERT INTO patients (
                    user_id, relation, source, needs_resolution,
                    display_name, sex, date_of_birth, legacy_age_group,
                    nosology, is_active, created_at, updated_at
                ) VALUES (
                    :user_id, 'self', 'legacy_migration', TRUE,
                    :display_name, NULL, NULL, :legacy_age_group,
                    :nosology, TRUE, :now, :now
                )
                RETURNING id
                """
            ),
            {
                "user_id": row.id,
                "display_name": row.first_name or "Пациент",
                "legacy_age_group": row.age_group,
                "nosology": row.nosology,
                "now": now,
            },
        ).scalar_one()

        conn.execute(
            text(
                """
                UPDATE symptom_entries
                SET patient_id = :patient_id
                WHERE user_id = :user_id AND patient_id IS NULL
                """
            ),
            {"patient_id": patient_id, "user_id": row.id},
        )

        conn.execute(
            text(
                """
                UPDATE users
                SET active_patient_id = :patient_id
                WHERE id = :user_id AND active_patient_id IS NULL
                """
            ),
            {"patient_id": patient_id, "user_id": row.id},
        )

    logger.info("Legacy schema catch-up complete")
