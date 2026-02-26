"""add whatsapp inbound media fields

Revision ID: 20260207_add_wa_media
Revises: 20260206_add_store_operating_hours
Create Date: 2026-02-07 10:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260207_add_wa_media"
down_revision = "20260206_add_store_operating_hours"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("whatsapp_inbound_messages", sa.Column("media_url", sa.Text(), nullable=True))
    op.add_column("whatsapp_inbound_messages", sa.Column("media_mime", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("whatsapp_inbound_messages", "media_mime")
    op.drop_column("whatsapp_inbound_messages", "media_url")
