"""init

Revision ID: 015452ad9d78
Revises:
Create Date: 2025-10-12 11:32:41.515413

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015452ad9d78"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
    )

    op.create_table(
        "blocked_days",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("date"),
    )

    op.create_table(
        "shipping_zip_ranges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("zip_start", sa.CHAR(length=8), nullable=False),
        sa.Column("zip_end", sa.CHAR(length=8), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("zip_start", "zip_end", name="uq_shipping_zip_range"),
    )

    op.create_table(
        "operations_config",
        sa.Column("id", sa.Boolean(), nullable=False),
        sa.Column("sla_minutes", sa.Integer(), nullable=False),
        sa.Column("delivery_enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "customer_addresses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("postal_code", sa.CHAR(length=8), nullable=False),
        sa.Column("street", sa.Text(), nullable=False),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("complement", sa.Text(), nullable=True),
        sa.Column("district", sa.Text(), nullable=True),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("state", sa.CHAR(length=2), nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("category_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("address_id", sa.String(length=36), nullable=True),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("shipping_cents", sa.Integer(), nullable=False),
        sa.Column("discount_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "received",
                "preparing",
                "ready",
                "on_route",
                "delivered",
                "completed",
                "canceled",
                name="orderstatus",
            ),
            nullable=False,
        ),
        sa.Column("delivery_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["address_id"], ["customer_addresses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "on_route", "delivered", "canceled", name="deliverystatus"),
            nullable=False,
        ),
        sa.Column("distance_km", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("eta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proof_url", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("method", sa.Enum("pix", "cash", name="paymentmethod"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "confirmed", "canceled", name="paymentstatus"),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("txid", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("order_items")
    op.drop_table("payments")
    op.drop_table("deliveries")
    op.drop_table("orders")
    op.drop_table("products")
    op.drop_table("customer_addresses")
    op.drop_table("operations_config")
    op.drop_table("shipping_zip_ranges")
    op.drop_table("blocked_days")
    op.drop_table("customers")
    op.drop_table("categories")
