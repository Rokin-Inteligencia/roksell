"""add campaigns table and link to orders

Revision ID: 20251212_add_campaigns
Revises: d8558b71228a
Create Date: 2025-12-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251212_add_campaigns"
down_revision: Union[str, Sequence[str], None] = "d8558b71228a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.Enum("order_percent", "shipping_percent", "category_percent", name="campaigntype"), nullable=False),
        sa.Column("value_percent", sa.Integer(), nullable=False),
        sa.Column("coupon_code", sa.String(length=64), nullable=True),
        sa.Column("category_id", sa.String(length=36), nullable=True),
        sa.Column("min_order_cents", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name="fk_campaign_category", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_campaign_tenant", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_tenant_coupon", "campaigns", ["tenant_id", "coupon_code"])
    op.create_index("ix_campaigns_tenant_active", "campaigns", ["tenant_id", "is_active", "starts_at", "ends_at"])

    op.add_column("orders", sa.Column("campaign_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_orders_campaign",
        "orders",
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_campaign", "orders", type_="foreignkey")
    op.drop_column("orders", "campaign_id")

    op.drop_index("ix_campaigns_tenant_active", table_name="campaigns")
    op.drop_index("ix_campaigns_tenant_coupon", table_name="campaigns")
    op.drop_table("campaigns")
    sa.Enum(name="campaigntype").drop(op.get_bind(), checkfirst=True)
