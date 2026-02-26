"""add whatsapp conversations and order message template

Revision ID: 20260125_whatsapp_window
Revises: 20260121_ops_cfg_finalstatuses
Create Date: 2026-01-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260125_whatsapp_window"
down_revision: Union[str, Sequence[str], None] = "20260121_ops_cfg_finalstatuses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("operations_config", sa.Column("whatsapp_order_message", sa.Text(), nullable=True))
    op.add_column("operations_config", sa.Column("whatsapp_last_read_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "whatsapp_conversations",
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id", "phone"),
    )
    op.create_table(
        "whatsapp_inbound_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("from_phone", sa.String(), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("message_type", sa.String(length=32), nullable=True),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_whatsapp_inbound_messages_tenant_id",
        "whatsapp_inbound_messages",
        ["tenant_id"],
    )
    op.create_index(
        "ix_whatsapp_inbound_messages_from_phone",
        "whatsapp_inbound_messages",
        ["from_phone"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_whatsapp_inbound_messages_from_phone", table_name="whatsapp_inbound_messages")
    op.drop_index("ix_whatsapp_inbound_messages_tenant_id", table_name="whatsapp_inbound_messages")
    op.drop_table("whatsapp_inbound_messages")
    op.drop_table("whatsapp_conversations")
    op.drop_column("operations_config", "whatsapp_last_read_at")
    op.drop_column("operations_config", "whatsapp_order_message")
