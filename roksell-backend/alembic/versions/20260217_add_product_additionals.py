"""add product additionals and product toggle

Revision ID: 20260217_add_product_additionals
Revises: 20260216_add_store_timezone
Create Date: 2026-02-17 11:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260217_add_product_additionals"
down_revision = "20260216_add_store_timezone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("additionals_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "additionals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("store_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "store_id", "name", name="uq_additional_name_store_tenant"),
    )
    op.create_index("ix_additionals_tenant_id", "additionals", ["tenant_id"])
    op.create_index("ix_additionals_store_id", "additionals", ["store_id"])

    op.create_table(
        "product_additionals",
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("additional_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["additional_id"], ["additionals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_id", "additional_id"),
    )
    op.create_index("ix_product_additionals_tenant_id", "product_additionals", ["tenant_id"])
    op.create_index("ix_product_additionals_additional_id", "product_additionals", ["additional_id"])


def downgrade() -> None:
    op.drop_index("ix_product_additionals_additional_id", table_name="product_additionals")
    op.drop_index("ix_product_additionals_tenant_id", table_name="product_additionals")
    op.drop_table("product_additionals")

    op.drop_index("ix_additionals_store_id", table_name="additionals")
    op.drop_index("ix_additionals_tenant_id", table_name="additionals")
    op.drop_table("additionals")

    op.drop_column("products", "additionals_enabled")
