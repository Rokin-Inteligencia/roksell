"""add operations_config whatsapp status message

Revision ID: 20260204_ops_cfg_wsp_status
Revises: 20260204_msg_cfg
Create Date: 2026-02-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260204_ops_cfg_wsp_status"
down_revision = "20260204_msg_cfg"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operations_config", sa.Column("whatsapp_status_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("operations_config", "whatsapp_status_message")
