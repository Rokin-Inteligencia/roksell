"""add whatsapp logs and order confirmed status

Revision ID: 20260116_whatsapp_logs
Revises: 20260116_ops_cfg_shipping_method
Create Date: 2026-01-16 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260116_whatsapp_logs"
down_revision: Union[str, Sequence[str], None] = "20260116_ops_cfg_shipping_method"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'confirmed'")
    op.create_table(
        "whatsapp_message_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("to_phone", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_whatsapp_message_logs_tenant_id",
        "whatsapp_message_logs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_whatsapp_message_logs_order_id",
        "whatsapp_message_logs",
        ["order_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_whatsapp_message_logs_order_id", table_name="whatsapp_message_logs")
    op.drop_index("ix_whatsapp_message_logs_tenant_id", table_name="whatsapp_message_logs")
    op.drop_table("whatsapp_message_logs")
