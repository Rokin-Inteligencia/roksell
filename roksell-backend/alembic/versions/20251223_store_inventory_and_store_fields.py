"""add store inventory and store metadata

Revision ID: 20251223_store_inventory
Revises: 20251213b
Create Date: 2025-12-23 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251223_store_inventory"
down_revision: Union[str, Sequence[str], None] = "20251213b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("postal_code", sa.CHAR(length=8), nullable=True))
    op.add_column("stores", sa.Column("street", sa.String(), nullable=True))
    op.add_column("stores", sa.Column("number", sa.String(), nullable=True))
    op.add_column("stores", sa.Column("district", sa.String(), nullable=True))
    op.add_column("stores", sa.Column("city", sa.String(), nullable=True))
    op.add_column("stores", sa.Column("state", sa.String(length=2), nullable=True))
    op.add_column("stores", sa.Column("complement", sa.String(), nullable=True))
    op.add_column("stores", sa.Column("reference", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("phone", sa.String(), nullable=True))
    op.add_column(
        "stores",
        sa.Column("is_delivery", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.alter_column("stores", "is_delivery", server_default=None)

    op.create_table(
        "store_inventory",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("store_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "store_id", "product_id", name="uq_inventory_store_product"),
    )

    op.add_column("users", sa.Column("default_store_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_users_default_store",
        "users",
        "stores",
        ["default_store_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("orders", sa.Column("store_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_orders_store",
        "orders",
        "stores",
        ["store_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_store", "orders", type_="foreignkey")
    op.drop_column("orders", "store_id")

    op.drop_constraint("fk_users_default_store", "users", type_="foreignkey")
    op.drop_column("users", "default_store_id")

    op.drop_table("store_inventory")

    op.drop_column("stores", "is_delivery")
    op.drop_column("stores", "phone")
    op.drop_column("stores", "reference")
    op.drop_column("stores", "complement")
    op.drop_column("stores", "state")
    op.drop_column("stores", "city")
    op.drop_column("stores", "district")
    op.drop_column("stores", "number")
    op.drop_column("stores", "street")
    op.drop_column("stores", "postal_code")
