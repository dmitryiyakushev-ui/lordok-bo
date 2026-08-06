"""Отметка о блокировке бота пользователем.

Revision ID: 0002_user_blocked_at
Revises: 0001_baseline
Create Date: 2026-08-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_user_blocked_at"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "blocked_at")
