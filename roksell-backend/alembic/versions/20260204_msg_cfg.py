"""add messaging config to operations_config

Revision ID: 20260204_msg_cfg
Revises: 20260204_pix_key
Create Date: 2026-02-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260204_msg_cfg"
down_revision = "20260204_pix_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operations_config", sa.Column("whatsapp_enabled", sa.Boolean(), nullable=True))
    op.add_column("operations_config", sa.Column("whatsapp_token", sa.Text(), nullable=True))
    op.add_column("operations_config", sa.Column("whatsapp_phone_number_id", sa.Text(), nullable=True))
    op.add_column("operations_config", sa.Column("telegram_enabled", sa.Boolean(), nullable=True))
    op.add_column("operations_config", sa.Column("telegram_bot_token", sa.Text(), nullable=True))
    op.add_column("operations_config", sa.Column("telegram_chat_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("operations_config", "telegram_chat_id")
    op.drop_column("operations_config", "telegram_bot_token")
    op.drop_column("operations_config", "telegram_enabled")
    op.drop_column("operations_config", "whatsapp_phone_number_id")
    op.drop_column("operations_config", "whatsapp_token")
    op.drop_column("operations_config", "whatsapp_enabled")
