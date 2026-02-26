"""add rule to campaigntype enum

Revision ID: 20260204_campaign_type_rule
Revises: 20260204_campaign_rules
Create Date: 2026-02-04 22:10:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260204_campaign_type_rule"
down_revision = "20260204_campaign_rules"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE campaigntype ADD VALUE IF NOT EXISTS 'rule'")


def downgrade():
    # PostgreSQL does not support removing enum values safely.
    pass
