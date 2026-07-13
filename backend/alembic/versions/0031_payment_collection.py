"""Add payment collection: tournament payment config + event_participants payment tracking.

Revision ID: 0031_payment_collection
Revises: 0030_tournament_members
"""

from alembic import op
import sqlalchemy as sa

revision = "0031_payment_collection"
down_revision = "0030_tournament_members"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tournaments", sa.Column("payment_amount", sa.Integer(), nullable=True))
    op.add_column("tournaments", sa.Column("payment_upi_id", sa.String(length=100), nullable=True))
    op.add_column("tournaments", sa.Column("payment_qr_url", sa.String(length=500), nullable=True))

    op.add_column("event_participants", sa.Column("payment_status", sa.String(length=20), nullable=False, server_default="not_required"))
    op.add_column("event_participants", sa.Column("payment_screenshot_url", sa.String(length=500), nullable=True))
    op.add_column("event_participants", sa.Column("payment_submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("event_participants", sa.Column("payment_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("event_participants", sa.Column("payment_confirmed_by", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True))


def downgrade():
    op.drop_column("event_participants", "payment_confirmed_by")
    op.drop_column("event_participants", "payment_confirmed_at")
    op.drop_column("event_participants", "payment_submitted_at")
    op.drop_column("event_participants", "payment_screenshot_url")
    op.drop_column("event_participants", "payment_status")

    op.drop_column("tournaments", "payment_qr_url")
    op.drop_column("tournaments", "payment_upi_id")
    op.drop_column("tournaments", "payment_amount")
