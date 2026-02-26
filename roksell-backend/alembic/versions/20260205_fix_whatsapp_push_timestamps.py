"""set defaults for whatsapp push subscription timestamps

Revision ID: 20260205_wa_push_ts_default
Revises: 20260205_wa_push_subs
Create Date: 2026-02-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260205_wa_push_ts_default"
down_revision = "20260205_wa_push_subs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "whatsapp_push_subscriptions",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )
    op.alter_column(
        "whatsapp_push_subscriptions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "whatsapp_push_subscriptions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "whatsapp_push_subscriptions",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
