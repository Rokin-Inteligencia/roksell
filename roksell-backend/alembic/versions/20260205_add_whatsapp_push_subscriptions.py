"""add whatsapp push subscriptions

Revision ID: 20260205_wa_push_subs
Revises: 20260205_wa_conv_name
Create Date: 2026-02-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260205_wa_push_subs"
down_revision = "20260205_wa_conv_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_push_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("expiration_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_whatsapp_push_subscriptions_tenant_id",
        "whatsapp_push_subscriptions",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_push_subscriptions_user_id",
        "whatsapp_push_subscriptions",
        ["user_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_whatsapp_push_subscriptions_tenant_endpoint",
        "whatsapp_push_subscriptions",
        ["tenant_id", "endpoint"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_whatsapp_push_subscriptions_tenant_endpoint",
        "whatsapp_push_subscriptions",
        type_="unique",
    )
    op.drop_index("ix_whatsapp_push_subscriptions_user_id", table_name="whatsapp_push_subscriptions")
    op.drop_index("ix_whatsapp_push_subscriptions_tenant_id", table_name="whatsapp_push_subscriptions")
    op.drop_table("whatsapp_push_subscriptions")
