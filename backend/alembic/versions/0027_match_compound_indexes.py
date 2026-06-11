"""Add compound indexes on matches for live-score query patterns.

Without these, every live-score poll does a full scan of the matches table
filtered by event_id then re-scanned for status/stage:
  - GET /public/t/{slug}  →  (event_id, status) for live-match filtering
  - Fixture sort queries  →  (event_id, stage, round) for bracket ordering

Revision ID: 0027_match_compound_indexes
Revises: 0026_more_indexes
"""

from alembic import op

revision = "0027_match_compound_indexes"
down_revision = "0026_more_indexes"
branch_labels = None
depends_on = None


def upgrade():
    # Covers: Match.event_id.in_([...]) + Match.status == "live"
    op.create_index(
        "ix_matches_event_status",
        "matches",
        ["event_id", "status"],
        if_not_exists=True,
    )
    # Covers: ORDER BY stage, round — lets Postgres sort in index order
    op.create_index(
        "ix_matches_event_round",
        "matches",
        ["event_id", "stage", "round"],
        if_not_exists=True,
    )


def downgrade():
    op.drop_index("ix_matches_event_status", table_name="matches")
    op.drop_index("ix_matches_event_round",  table_name="matches")
