"""Collapse the 5-value tournament lifecycle down to draft/live/completed.

The old model had TOURNAMENT_STATUSES = [draft, registration, fixtures, live,
completed] but the transition endpoint's allowed-transitions table used
"upcoming"/"done" instead of "fixtures"/"completed" as target names — a
mismatch that made most transitions 400 forever (organisers could reach
"registration" but could never reach "live" from some paths, and "done" was
completely unreachable). Registration availability is now computed from
registration_start_date/registration_end_date instead of being a lifecycle
state, so "registration" collapses into "live" (with registration open) and
"fixtures"/"upcoming" collapse into "live" (registration not necessarily
open). "done" (never actually reachable) and any manually-set "completed"
rows both map to "completed".

Revision ID: 0028_simplify_tournament_status
Revises: 0027_match_compound_indexes
"""

from alembic import op
import sqlalchemy as sa

revision = "0028_simplify_tournament_status"
down_revision = "0027_match_compound_indexes"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE tournaments SET status = 'live' "
        "WHERE status IN ('registration', 'upcoming', 'fixtures')"
    ))
    conn.execute(sa.text(
        "UPDATE tournaments SET status = 'completed' WHERE status = 'done'"
    ))


def downgrade():
    # Old 5-value granularity is not recoverable — this is a lossy collapse.
    pass
