"""
Runtime schema migrations.

Runs after `Base.metadata.create_all()` to:
1. Add new columns to pre-existing tables (create_all does not alter them).
2. Backfill a legacy Patient row for each old-format user.
3. Rewire legacy symptom_entries to the new patient_id.

All steps are idempotent: repeated runs are safe.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def _column_exists(conn, table: str, column: str) -> bool:
    result = await conn.execute(
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


async def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    if not await _column_exists(conn, table, column):
        logger.info("Adding column %s.%s", table, column)
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


async def _add_fk_if_missing(
    conn,
    table: str,
    constraint_name: str,
    ddl: str,
) -> None:
    result = await conn.execute(
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
        await conn.execute(
            text(f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} {ddl}")
        )


async def run_runtime_migrations(engine: AsyncEngine) -> None:
    """Apply schema additions and legacy backfill. Idempotent."""
    async with engine.begin() as conn:
        # ── users: new columns ──
        await _add_column_if_missing(conn, "users", "full_name", "VARCHAR(255)")
        await _add_column_if_missing(conn, "users", "phone", "VARCHAR(32)")
        await _add_column_if_missing(
            conn, "users", "active_patient_id", "INTEGER"
        )
        await _add_fk_if_missing(
            conn,
            "users",
            "users_active_patient_id_fkey",
            "FOREIGN KEY (active_patient_id) REFERENCES patients(id) ON DELETE SET NULL",
        )

        # ── users: timezone ──
        await _add_column_if_missing(
            conn, "users", "user_tz", "VARCHAR(50) DEFAULT 'Europe/Moscow'"
        )

        # ── symptom_entries: patient_id ──
        await _add_column_if_missing(
            conn, "symptom_entries", "patient_id", "INTEGER"
        )
        await _add_fk_if_missing(
            conn,
            "symptom_entries",
            "symptom_entries_patient_id_fkey",
            "FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE",
        )

        # Index on patient_id if missing (Postgres creates automatically only for PKs/FKs to PK)
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_symptom_entries_patient_id "
                "ON symptom_entries (patient_id)"
            )
        )

        # ── symptom_entries: user_notes (free-text patient comment) ──
        await _add_column_if_missing(
            conn, "symptom_entries", "user_notes", "TEXT"
        )

        # ── symptom_entries: treatment context (diagnosed patients) ──
        await _add_column_if_missing(
            conn, "symptom_entries", "last_doctor_visit", "INTEGER"
        )
        await _add_column_if_missing(
            conn, "symptom_entries", "treatment_status", "VARCHAR(20)"
        )

        # ── scale_scores table (new: Centor, FeverPAIN, SNOT-22, etc.) ──
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS scale_scores (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
                    scale VARCHAR(16) NOT NULL,
                    score INTEGER NOT NULL,
                    details JSONB DEFAULT '{}',
                    action VARCHAR(32),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_scale_scores_user_id ON scale_scores (user_id)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_scale_scores_patient_id ON scale_scores (patient_id)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_scale_scores_scale ON scale_scores (scale)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_scale_scores_created_at ON scale_scores (created_at)")
        )

        # ── episode_logs table (new: tonsillitis, AOM, CRS flare episodes) ──
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS episode_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
                    episode_type VARCHAR(32) NOT NULL,
                    confirmed_by_doctor BOOLEAN DEFAULT FALSE,
                    scale_score INTEGER,
                    started_at TIMESTAMPTZ DEFAULT NOW(),
                    ended_at TIMESTAMPTZ,
                    notes TEXT
                )
                """
            )
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_episode_logs_user_id ON episode_logs (user_id)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_episode_logs_patient_id ON episode_logs (patient_id)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_episode_logs_episode_type ON episode_logs (episode_type)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_episode_logs_started_at ON episode_logs (started_at)")
        )

        # ── patients: case_closed_at (manual case closure) ──
        await _add_column_if_missing(
            conn, "patients", "case_closed_at", "TIMESTAMPTZ"
        )

        # ── Legacy backfill ──
        # A "legacy user" is one who has a nosology set but no Patient rows yet.
        now = datetime.now(timezone.utc)

        result = await conn.execute(
            text(
                """
                SELECT u.id, u.first_name, u.nosology, u.age_group
                FROM users u
                LEFT JOIN patients p ON p.user_id = u.id
                WHERE u.nosology IS NOT NULL AND p.id IS NULL
                """
            )
        )
        legacy_users = result.fetchall()

        if legacy_users:
            logger.info(
                "Backfilling %d legacy user(s) into patients table",
                len(legacy_users),
            )

        for row in legacy_users:
            user_id = row.id
            display_name = row.first_name or "Пациент"
            nosology = row.nosology
            age_group = row.age_group

            # Create the legacy patient record
            insert_result = await conn.execute(
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
                    "user_id": user_id,
                    "display_name": display_name,
                    "legacy_age_group": age_group,
                    "nosology": nosology,
                    "now": now,
                },
            )
            patient_id = insert_result.scalar_one()

            # Rewire this user's symptom_entries that have no patient_id
            await conn.execute(
                text(
                    """
                    UPDATE symptom_entries
                    SET patient_id = :patient_id
                    WHERE user_id = :user_id AND patient_id IS NULL
                    """
                ),
                {"patient_id": patient_id, "user_id": user_id},
            )

            # Mark this user's active_patient_id only if currently NULL
            await conn.execute(
                text(
                    """
                    UPDATE users
                    SET active_patient_id = :patient_id
                    WHERE id = :user_id AND active_patient_id IS NULL
                    """
                ),
                {"patient_id": patient_id, "user_id": user_id},
            )

        logger.info("Runtime migrations complete.")
