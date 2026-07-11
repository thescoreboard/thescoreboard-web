"""Add tournament_members and tournament_invites tables.

Revision ID: 0030_tournament_members
Revises: 0029_sponsor_contact_email
"""

from alembic import op
import sqlalchemy as sa

revision = "0030_tournament_members"
down_revision = "0029_sponsor_contact_email"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tournament_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="staff"),
        sa.Column("invited_by", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tournament_id", "user_id", name="uq_tournament_user"),
    )
    op.create_index("ix_tournament_members_tournament_id", "tournament_members", ["tournament_id"])
    op.create_index("ix_tournament_members_user_id", "tournament_members", ["user_id"])

    op.create_table(
        "tournament_invites",
        sa.Column("invite_id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_tournament_invites_token", "tournament_invites", ["token"], unique=True)
    op.create_index("ix_tournament_invites_tournament_id", "tournament_invites", ["tournament_id"])


def downgrade():
    op.drop_index("ix_tournament_invites_tournament_id", table_name="tournament_invites")
    op.drop_index("ix_tournament_invites_token", table_name="tournament_invites")
    op.drop_table("tournament_invites")
    op.drop_index("ix_tournament_members_user_id", table_name="tournament_members")
    op.drop_index("ix_tournament_members_tournament_id", table_name="tournament_members")
    op.drop_table("tournament_members")
