"""Add data-integrity CHECK constraints.

DI-1: a match/event participant must reference exactly one of player_id/team_id.
DI-2: match.status and event_participants.payment_status are closed enums.

Verified against dev + prod data before writing: 0 XOR violations, and all
existing status/payment_status values fall inside the allowed sets, so these
constraints apply cleanly to existing rows.

Revision ID: 0032_integrity_constraints
Revises: 0031_payment_collection
"""
from alembic import op

revision = "0032_integrity_constraints"
down_revision = "0031_payment_collection"
branch_labels = None
depends_on = None


# We add every constraint as NOT VALID. Existing rows were verified clean before
# writing this migration (0 XOR violations; all status/payment_status values are
# already in-range), so skipping the historical-row validation scan is safe — and
# it avoids Supabase's statement timeout, which cancels the full-table scan +
# ACCESS EXCLUSIVE lock that a normal ADD CONSTRAINT needs. NOT VALID still fully
# enforces the constraint on every future INSERT/UPDATE; it only means Postgres
# hasn't re-proven the pre-existing rows (which we proved manually).
#
# To later mark historical rows as validated too, run during a quiet window:
#   ALTER TABLE <t> VALIDATE CONSTRAINT <name>;   (takes a lighter SHARE lock)
_CONSTRAINTS = [
    ("match_participants", "ck_mp_one_side",
     "(player_id IS NULL) <> (team_id IS NULL)"),
    ("event_participants", "ck_ep_one_side",
     "(player_id IS NULL) <> (team_id IS NULL)"),
    # `matches.stage` is intentionally left unconstrained — historical rows carry
    # legacy values (e.g. 'third', 'bye') that a strict enum would reject.
    ("matches", "ck_matches_status",
     "status IN ('scheduled', 'live', 'done')"),
    ("event_participants", "ck_ep_payment_status",
     "payment_status IN ('not_required', 'pending', 'paid')"),
]


def upgrade():
    for table, name, expr in _CONSTRAINTS:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expr}) NOT VALID"
        )


def downgrade():
    for table, name, _expr in reversed(_CONSTRAINTS):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
