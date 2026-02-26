"""add whatsapp conversation last_read_at

Revision ID: 20260205_wa_conv_last_read
Revises: 20260205_wa_push_ts_default
Create Date: 2026-02-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260205_wa_conv_last_read"
down_revision = "20260205_wa_push_ts_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("whatsapp_conversations", sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("whatsapp_conversations", "last_read_at")
