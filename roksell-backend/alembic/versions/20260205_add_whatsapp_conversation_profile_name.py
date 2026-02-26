"""add whatsapp conversation profile name

Revision ID: 20260205_wa_conv_name
Revises: 20260204_ops_cfg_wsp_status
Create Date: 2026-02-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260205_wa_conv_name"
down_revision = "20260204_ops_cfg_wsp_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("whatsapp_conversations", sa.Column("profile_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("whatsapp_conversations", "profile_name")
