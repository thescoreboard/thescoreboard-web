"""Add indexes on remaining hot FK / filter columns.

Without these indexes the following queries do full table scans:
  - GET /auth/my-tournaments → MatchParticipant.player_id
  - GET /auth/my-stats       → MatchParticipant.player_id / team_id
  - GET /players?org_id=...  → Player.org_id, Team.org_id
  - GET /teams/:id/members   → TeamMember.team_id
  - GET /sponsors?tournament → Sponsor.tournament_id
  - Group-stage pages        → EventParticipant.player_id / team_id, Standing.event_id / group_id

Revision ID: 0026_more_indexes
Revises: 0025_add_missing_indexes
"""

from alembic import op

revision = "0026_more_indexes"
down_revision = "0025_add_missing_indexes"
branch_labels = None
depends_on = None


def upgrade():
    # MatchParticipant — player stats queries filter by player_id / team_id
    op.create_index("ix_match_participants_player_id", "match_participants", ["player_id"], if_not_exists=True)
    op.create_index("ix_match_participants_team_id",   "match_participants", ["team_id"],   if_not_exists=True)

    # Player / Team — org roster lookups filter by org_id
    op.create_index("ix_players_org_id", "players", ["org_id"], if_not_exists=True)
    op.create_index("ix_teams_org_id",   "teams",   ["org_id"], if_not_exists=True)

    # TeamMember — roster fetch by team_id
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"], if_not_exists=True)

    # Sponsor — tournament sponsor listing
    op.create_index("ix_sponsors_tournament_id", "sponsors", ["tournament_id"], if_not_exists=True)

    # EventParticipant — group-stage / standings queries
    op.create_index("ix_event_participants_player_id", "event_participants", ["player_id"], if_not_exists=True)
    op.create_index("ix_event_participants_team_id",   "event_participants", ["team_id"],   if_not_exists=True)

    # Standing — points-table queries filter by event_id + group_id
    op.create_index("ix_standings_event_id", "standings", ["event_id"], if_not_exists=True)
    op.create_index("ix_standings_group_id", "standings", ["group_id"], if_not_exists=True)


def downgrade():
    op.drop_index("ix_match_participants_player_id", table_name="match_participants")
    op.drop_index("ix_match_participants_team_id",   table_name="match_participants")
    op.drop_index("ix_players_org_id",               table_name="players")
    op.drop_index("ix_teams_org_id",                 table_name="teams")
    op.drop_index("ix_team_members_team_id",         table_name="team_members")
    op.drop_index("ix_sponsors_tournament_id",       table_name="sponsors")
    op.drop_index("ix_event_participants_player_id", table_name="event_participants")
    op.drop_index("ix_event_participants_team_id",   table_name="event_participants")
    op.drop_index("ix_standings_event_id",           table_name="standings")
    op.drop_index("ix_standings_group_id",           table_name="standings")
