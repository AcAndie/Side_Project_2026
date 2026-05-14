"""add job resume columns

Revision ID: a1b2c3d4e5f6
Revises: 63fc07004d91
Create Date: 2026-05-14 12:00:00.000000

Adds batch-progress columns to ``jobs`` so a crashed batch can resume from the
last completed chapter index instead of restarting from zero.

  - ``total_count``           — total chapters in the batch (immutable once set)
  - ``completed_count``       — chapters successfully persisted
  - ``failed_count``          — chapters skipped due to per-chapter error
  - ``last_completed_index``  — 0-based offset of the last successful chapter;
                                ``-1`` means none yet, resume starts at 0
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "63fc07004d91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("total_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "last_completed_index",
                sa.Integer(),
                nullable=False,
                server_default="-1",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_column("last_completed_index")
        batch_op.drop_column("failed_count")
        batch_op.drop_column("completed_count")
        batch_op.drop_column("total_count")
