"""Add contact_email to sponsors.

Revision ID: 0029_sponsor_contact_email
Revises: 0028_simplify_tournament_status
"""

from alembic import op
import sqlalchemy as sa

revision = "0029_sponsor_contact_email"
down_revision = "0028_simplify_tournament_status"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sponsors", sa.Column("contact_email", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("sponsors", "contact_email")
