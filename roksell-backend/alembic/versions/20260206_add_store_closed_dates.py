"""add store closed dates

Revision ID: 20260206_add_store_closed_dates
Revises: 20260204_campaign_type_rule, 20260205_wa_conv_last_read
Create Date: 2026-02-06 00:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260206_add_store_closed_dates"
down_revision = ("20260204_campaign_type_rule", "20260205_wa_conv_last_read")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("closed_dates", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stores", "closed_dates")
