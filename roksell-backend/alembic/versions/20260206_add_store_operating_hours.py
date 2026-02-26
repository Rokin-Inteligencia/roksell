"""add store operating hours

Revision ID: 20260206_add_store_operating_hours
Revises: 20260206_add_store_closed_dates
Create Date: 2026-02-06 00:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260206_add_store_operating_hours"
down_revision = "20260206_add_store_closed_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("operating_hours", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stores", "operating_hours")
