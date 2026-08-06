"""Базовая ревизия: схема ЛОРдока на момент перехода на alembic.

На пустой базе создаёт все таблицы. На базе, которая осталась от
прежней схемы (create_all плюс ALTER TABLE при старте), вместо этого
догоняет недостающие колонки и переносит легаси-пользователей в
таблицу пациентов.

Дальше схема живёт обычными ревизиями.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-06
"""

import sqlalchemy as sa
from alembic import op

from bot.db.legacy_schema import catch_up

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _database_is_empty() -> bool:
    """Есть ли в базе таблица users, то есть работал ли бот раньше."""
    conn = op.get_bind()
    return not sa.inspect(conn).has_table("users")


def upgrade() -> None:
    if _database_is_empty():
        _create_schema()
        return

    # Старая база: таблицы на месте, не хватает колонок и переноса.
    catch_up(op.get_bind())


def downgrade() -> None:
    raise NotImplementedError(
        "Базовая ревизия не откатывается: она сносила бы всю базу целиком."
    )


def _create_schema() -> None:
    op.create_table('bot_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=True),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bot_events_created_at'), 'bot_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_bot_events_event_type'), 'bot_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_bot_events_user_id'), 'bot_events', ['user_id'], unique=False)
    op.create_table('feedbacks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('rating', sa.SmallInteger(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_feedbacks_created_at'), 'feedbacks', ['created_at'], unique=False)
    op.create_index(op.f('ix_feedbacks_user_id'), 'feedbacks', ['user_id'], unique=False)
    op.create_table('patients',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('relation', sa.String(length=10), nullable=False, comment="'self' | 'child'"),
    sa.Column('source', sa.String(length=20), nullable=False, comment="'user_added' | 'legacy_migration'"),
    sa.Column('needs_resolution', sa.Boolean(), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('sex', sa.String(length=1), nullable=True, comment="'m' | 'f' | None"),
    sa.Column('date_of_birth', sa.Date(), nullable=True),
    sa.Column('legacy_age_group', sa.String(length=10), nullable=True, comment='Transitional attribute for legacy records only'),
    sa.Column('nosology', sa.String(length=50), nullable=True, comment='ars, crs, tonsillopharyngitis, aom, com, adenoid_hypertrophy, undiagnosed_*'),
    sa.Column('case_closed_at', sa.DateTime(timezone=True), nullable=True, comment='Set when patient closes current case; cleared on next diary fill'),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_patients_user_id'), 'patients', ['user_id'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('username', sa.String(length=255), nullable=True),
    sa.Column('first_name', sa.String(length=255), nullable=False),
    sa.Column('language_code', sa.String(length=10), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('source', sa.String(length=64), nullable=True),
    sa.Column('consent_version', sa.String(length=16), nullable=True),
    sa.Column('consent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('active_patient_id', sa.Integer(), nullable=True),
    sa.Column('nosology', sa.String(length=50), nullable=True),
    sa.Column('age_group', sa.String(length=10), nullable=True),
    sa.Column('reminder_time', sa.Time(), nullable=False),
    sa.Column('user_tz', sa.String(length=50), nullable=False),
    sa.Column('is_premium', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['active_patient_id'], ['patients.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('episode_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=True),
    sa.Column('episode_type', sa.String(length=32), nullable=False),
    sa.Column('confirmed_by_doctor', sa.Boolean(), nullable=False),
    sa.Column('scale_score', sa.Integer(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_episode_logs_episode_type'), 'episode_logs', ['episode_type'], unique=False)
    op.create_index(op.f('ix_episode_logs_patient_id'), 'episode_logs', ['patient_id'], unique=False)
    op.create_index(op.f('ix_episode_logs_started_at'), 'episode_logs', ['started_at'], unique=False)
    op.create_index(op.f('ix_episode_logs_user_id'), 'episode_logs', ['user_id'], unique=False)
    op.create_table('scale_scores',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=True),
    sa.Column('scale', sa.String(length=16), nullable=False),
    sa.Column('score', sa.Integer(), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('action', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scale_scores_created_at'), 'scale_scores', ['created_at'], unique=False)
    op.create_index(op.f('ix_scale_scores_patient_id'), 'scale_scores', ['patient_id'], unique=False)
    op.create_index(op.f('ix_scale_scores_scale'), 'scale_scores', ['scale'], unique=False)
    op.create_index(op.f('ix_scale_scores_user_id'), 'scale_scores', ['user_id'], unique=False)
    op.create_table('symptom_entries',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=True),
    sa.Column('nosology', sa.String(length=50), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('symptoms', sa.JSON(), nullable=False),
    sa.Column('composite_score', sa.Integer(), nullable=False),
    sa.Column('triage_level', sa.String(length=20), nullable=False),
    sa.Column('triage_message', sa.Text(), nullable=False),
    sa.Column('red_flags', sa.JSON(), nullable=False),
    sa.Column('last_doctor_visit', sa.Integer(), nullable=True),
    sa.Column('treatment_status', sa.String(length=20), nullable=True),
    sa.Column('user_notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_symptom_entries_nosology'), 'symptom_entries', ['nosology'], unique=False)
    op.create_index(op.f('ix_symptom_entries_patient_id'), 'symptom_entries', ['patient_id'], unique=False)
    op.create_index(op.f('ix_symptom_entries_recorded_at'), 'symptom_entries', ['recorded_at'], unique=False)
    op.create_index(op.f('ix_symptom_entries_triage_level'), 'symptom_entries', ['triage_level'], unique=False)
    op.create_index(op.f('ix_symptom_entries_user_id'), 'symptom_entries', ['user_id'], unique=False)
