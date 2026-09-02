"""Partial index for the hot public listing pattern.

The homepage, sport pages, and search all filter `is_active = true` and sort
by `created_at DESC`. A partial index covers exactly that: it only contains
active rows (small) and hands Postgres pre-sorted output, skipping both the
filter and the sort. Inactive/archived tournaments never bloat it.

Revision ID: 0033_active_tournaments_index
Revises: 0032_integrity_constraints
"""
from alembic import op

revision = "0033_active_tournaments_index"
down_revision = "0032_integrity_constraints"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tournaments_active_created "
        "ON tournaments (created_at DESC) WHERE is_active"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_tournaments_active_created")
