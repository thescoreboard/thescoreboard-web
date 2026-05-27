"""Add missing indexes on hot query columns.

Without these indexes the following queries do full table scans:
  - GET /dashboard  → OrgMember.user_id, Tournament.org_id
  - GET /public/home → Tournament.is_active, Tournament.status
  - Fixture queries  → Event.tournament_id, Event.is_active

Revision ID: 0025_add_missing_indexes
Revises: 0024_backfill_is_active
"""

from alembic import op

revision = "0025_add_missing_indexes"
down_revision = "0024_backfill_is_active"
branch_labels = None
depends_on = None


def upgrade():
    # OrgMember — dashboard query filters by user_id and org_id
    op.create_index("ix_org_members_user_id",   "org_members",  ["user_id"],      if_not_exists=True)
    op.create_index("ix_org_members_org_id",    "org_members",  ["org_id"],       if_not_exists=True)

    # Tournament — dashboard filters by org_id; homepage by is_active + status
    op.create_index("ix_tournaments_org_id",    "tournaments",  ["org_id"],       if_not_exists=True)
    op.create_index("ix_tournaments_is_active", "tournaments",  ["is_active"],    if_not_exists=True)
    op.create_index("ix_tournaments_status",    "tournaments",  ["status"],       if_not_exists=True)

    # Event — joinedload and sport-page queries use tournament_id + is_active
    op.create_index("ix_events_tournament_id",  "events",       ["tournament_id"], if_not_exists=True)
    op.create_index("ix_events_is_active",      "events",       ["is_active"],     if_not_exists=True)


def downgrade():
    op.drop_index("ix_org_members_user_id",   table_name="org_members")
    op.drop_index("ix_org_members_org_id",    table_name="org_members")
    op.drop_index("ix_tournaments_org_id",    table_name="tournaments")
    op.drop_index("ix_tournaments_is_active", table_name="tournaments")
    op.drop_index("ix_tournaments_status",    table_name="tournaments")
    op.drop_index("ix_events_tournament_id",  table_name="events")
    op.drop_index("ix_events_is_active",      table_name="events")
