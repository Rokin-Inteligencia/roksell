"""add campaign rules and store scope

Revision ID: 20260204_campaign_rules
Revises: 20260204_msg_cfg
Create Date: 2026-02-04 21:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260204_campaign_rules"
down_revision = "20260204_msg_cfg"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("campaigns", sa.Column("rule_config", sa.Text(), nullable=True))
    op.add_column("campaigns", sa.Column("apply_mode", sa.String(length=16), nullable=False, server_default="first"))
    op.add_column("campaigns", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "campaign_stores",
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True),
    )

    # Drop server defaults after backfilling
    op.alter_column("campaigns", "apply_mode", server_default=None)
    op.alter_column("campaigns", "priority", server_default=None)


def downgrade():
    op.drop_table("campaign_stores")
    op.drop_column("campaigns", "priority")
    op.drop_column("campaigns", "apply_mode")
    op.drop_column("campaigns", "rule_config")
