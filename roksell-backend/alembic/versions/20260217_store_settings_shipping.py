"""move operational settings and shipping tiers to store scope

Revision ID: 20260217_store_settings_shipping
Revises: 20260217_add_product_additionals
Create Date: 2026-02-17 22:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260217_store_settings_shipping"
down_revision = "20260217_add_product_additionals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stores",
        sa.Column("sla_minutes", sa.Integer(), nullable=False, server_default="45"),
    )
    op.add_column("stores", sa.Column("cover_image_url", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("whatsapp_contact_phone", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("payment_methods", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("order_statuses", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("order_status_canceled_color", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("order_status_colors", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("order_final_statuses", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("shipping_method", sa.Text(), nullable=True))
    op.add_column(
        "stores",
        sa.Column("shipping_fixed_fee_cents", sa.Integer(), nullable=False, server_default="0"),
    )

    op.execute(
        sa.text(
            """
            UPDATE stores
            SET
                sla_minutes = COALESCE((
                    SELECT operations_config.sla_minutes
                    FROM operations_config
                    WHERE operations_config.tenant_id = stores.tenant_id
                ), 45),
                cover_image_url = (
                    SELECT operations_config.cover_image_url
                    FROM operations_config
                    WHERE operations_config.tenant_id = stores.tenant_id
                ),
                whatsapp_contact_phone = (
                    SELECT operations_config.whatsapp_contact_phone
                    FROM operations_config
                    WHERE operations_config.tenant_id = stores.tenant_id
                ),
                payment_methods = (
                    SELECT operations_config.payment_methods
                    FROM operations_config
                    WHERE operations_config.tenant_id = stores.tenant_id
                ),
                order_statuses = (
                    SELECT operations_config.order_statuses
                    FROM operations_config
                    WHERE operations_config.tenant_id = stores.tenant_id
                ),
                order_status_canceled_color = (
                    SELECT operations_config.order_status_canceled_color
                    FROM operations_config
                    WHERE operations_config.tenant_id = stores.tenant_id
                ),
                order_status_colors = (
                    SELECT operations_config.order_status_colors
                    FROM operations_config
                    WHERE operations_config.tenant_id = stores.tenant_id
                ),
                order_final_statuses = (
                    SELECT operations_config.order_final_statuses
                    FROM operations_config
                    WHERE operations_config.tenant_id = stores.tenant_id
                ),
                shipping_method = (
                    SELECT operations_config.shipping_method
                    FROM operations_config
                    WHERE operations_config.tenant_id = stores.tenant_id
                )
            """
        )
    )

    op.add_column(
        "shipping_distance_tiers",
        sa.Column("store_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_shipping_distance_tiers_store_id",
        "shipping_distance_tiers",
        ["store_id"],
    )
    op.create_foreign_key(
        "fk_shipping_distance_tiers_store_id",
        "shipping_distance_tiers",
        "stores",
        ["store_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("uq_shipping_distance_interval", "shipping_distance_tiers", type_="unique")
    op.create_unique_constraint(
        "uq_shipping_distance_interval",
        "shipping_distance_tiers",
        ["tenant_id", "store_id", "km_min", "km_max"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_shipping_distance_interval", "shipping_distance_tiers", type_="unique")
    op.create_unique_constraint(
        "uq_shipping_distance_interval",
        "shipping_distance_tiers",
        ["tenant_id", "km_min", "km_max"],
    )
    op.drop_constraint("fk_shipping_distance_tiers_store_id", "shipping_distance_tiers", type_="foreignkey")
    op.drop_index("ix_shipping_distance_tiers_store_id", table_name="shipping_distance_tiers")
    op.drop_column("shipping_distance_tiers", "store_id")

    op.drop_column("stores", "shipping_fixed_fee_cents")
    op.drop_column("stores", "shipping_method")
    op.drop_column("stores", "order_final_statuses")
    op.drop_column("stores", "order_status_colors")
    op.drop_column("stores", "order_status_canceled_color")
    op.drop_column("stores", "order_statuses")
    op.drop_column("stores", "payment_methods")
    op.drop_column("stores", "whatsapp_contact_phone")
    op.drop_column("stores", "cover_image_url")
    op.drop_column("stores", "sla_minutes")
