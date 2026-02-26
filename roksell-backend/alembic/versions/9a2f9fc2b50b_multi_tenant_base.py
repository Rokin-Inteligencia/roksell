"""multi tenant base tables and scoping

Revision ID: 9a2f9fc2b50b
Revises: 4433bd3f30c7
Create Date: 2025-11-15 12:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import table, column


revision = "9a2f9fc2b50b"
down_revision = "4433bd3f30c7"
branch_labels = None
depends_on = None

LEGACY_TENANT_ID = "00000000-0000-0000-0000-000000000001"

tenant_status_enum = postgresql.ENUM("active", "suspended", "canceled", name="tenantstatus", create_type=False)


def _add_tenant_column(table_name: str, *, index: bool = True) -> None:
    op.add_column(table_name, sa.Column("tenant_id", sa.String(length=36), nullable=True))
    if index:
        op.create_index(f"ix_{table_name}_tenant_id", table_name, ["tenant_id"])
    stmt = sa.text(f"UPDATE {table_name} SET tenant_id = :tenant").bindparams(tenant=LEGACY_TENANT_ID)
    op.execute(stmt)
    op.alter_column(table_name, "tenant_id", existing_type=sa.String(length=36), nullable=False)
    op.create_foreign_key(
        f"fk_{table_name}_tenant_id",
        table_name,
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def upgrade() -> None:
    bind = op.get_bind()
    enum_type = postgresql.ENUM("active", "suspended", "canceled", name="tenantstatus", create_type=True)
    enum_type.create(bind, checkfirst=True)

    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("status", tenant_status_enum, nullable=False, server_default="active"),
        sa.Column("timezone", sa.String(), nullable=False, server_default="America/Sao_Paulo"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="BRL"),
        sa.Column("default_locale", sa.String(length=5), nullable=False, server_default="pt-BR"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "tenant_modules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "module", name="uq_tenant_module"),
    )
    op.create_index("ix_tenant_modules_tenant_id", "tenant_modules", ["tenant_id"])

    tenants_table = table(
        "tenants",
        column("id", sa.String(length=36)),
        column("name", sa.String()),
        column("slug", sa.String()),
        column("status", tenant_status_enum),
        column("timezone", sa.String()),
        column("currency", sa.String(length=3)),
        column("default_locale", sa.String(length=5)),
    )
    op.bulk_insert(
        tenants_table,
        [
            {
                "id": LEGACY_TENANT_ID,
                "name": "Legacy Tenant",
                "slug": "legacy",
                "status": "active",
                "timezone": "America/Sao_Paulo",
                "currency": "BRL",
                "default_locale": "pt-BR",
            }
        ],
    )

    _add_tenant_column("categories")
    op.drop_constraint("categories_name_key", "categories", type_="unique")
    op.create_unique_constraint("uq_category_name_tenant", "categories", ["tenant_id", "name"])

    _add_tenant_column("products")

    _add_tenant_column("customers")
    op.drop_constraint("customers_phone_key", "customers", type_="unique")
    op.create_unique_constraint("uq_customer_phone_tenant", "customers", ["tenant_id", "phone"])

    _add_tenant_column("customer_addresses")
    _add_tenant_column("orders")
    _add_tenant_column("order_items")
    _add_tenant_column("payments")
    _add_tenant_column("deliveries")
    _add_tenant_column("stores")

    _add_tenant_column("shipping_distance_tiers")
    op.drop_constraint("uq_shipping_distance_interval", "shipping_distance_tiers", type_="unique")
    op.create_unique_constraint(
        "uq_shipping_distance_interval",
        "shipping_distance_tiers",
        ["tenant_id", "km_min", "km_max"],
    )

    _add_tenant_column("shipping_overrides")
    op.create_unique_constraint("uq_shipping_override_postal_code", "shipping_overrides", ["tenant_id", "postal_code"])

    op.add_column("operations_config", sa.Column("tenant_id", sa.String(length=36), nullable=True))
    op.execute(
        sa.text("UPDATE operations_config SET tenant_id = :tenant").bindparams(tenant=LEGACY_TENANT_ID)
    )
    op.alter_column("operations_config", "tenant_id", existing_type=sa.String(length=36), nullable=False)
    op.drop_constraint("operations_config_pkey", "operations_config", type_="primary")
    op.drop_column("operations_config", "id")
    op.create_primary_key("operations_config_pkey", "operations_config", ["tenant_id"])
    op.create_foreign_key(
        "fk_operations_config_tenant_id",
        "operations_config",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column("blocked_days", sa.Column("tenant_id", sa.String(length=36), nullable=True))
    op.execute(sa.text("UPDATE blocked_days SET tenant_id = :tenant").bindparams(tenant=LEGACY_TENANT_ID))
    op.alter_column("blocked_days", "tenant_id", existing_type=sa.String(length=36), nullable=False)
    op.drop_constraint("blocked_days_pkey", "blocked_days", type_="primary")
    op.create_primary_key("blocked_days_pkey", "blocked_days", ["tenant_id", "date"])
    op.create_foreign_key(
        "fk_blocked_days_tenant_id",
        "blocked_days",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_blocked_days_tenant_id", "blocked_days", type_="foreignkey")
    op.drop_constraint("blocked_days_pkey", "blocked_days", type_="primary")
    op.drop_column("blocked_days", "tenant_id")
    op.create_primary_key("blocked_days_pkey", "blocked_days", ["date"])

    op.drop_constraint("fk_operations_config_tenant_id", "operations_config", type_="foreignkey")
    op.drop_constraint("operations_config_pkey", "operations_config", type_="primary")
    op.add_column("operations_config", sa.Column("id", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_primary_key("operations_config_pkey", "operations_config", ["id"])
    op.drop_column("operations_config", "tenant_id")

    op.drop_constraint("uq_shipping_override_postal_code", "shipping_overrides", type_="unique")
    op.drop_constraint("fk_shipping_overrides_tenant_id", "shipping_overrides", type_="foreignkey")
    op.drop_index("ix_shipping_overrides_tenant_id", table_name="shipping_overrides")
    op.drop_column("shipping_overrides", "tenant_id")

    op.drop_constraint("uq_shipping_distance_interval", "shipping_distance_tiers", type_="unique")
    op.drop_constraint("fk_shipping_distance_tiers_tenant_id", "shipping_distance_tiers", type_="foreignkey")
    op.drop_index("ix_shipping_distance_tiers_tenant_id", table_name="shipping_distance_tiers")
    op.drop_column("shipping_distance_tiers", "tenant_id")
    op.create_unique_constraint("uq_shipping_distance_interval", "shipping_distance_tiers", ["km_min", "km_max"])

    for table in [
        "stores",
        "deliveries",
        "payments",
        "order_items",
        "orders",
        "customer_addresses",
        "customers",
        "products",
        "categories",
    ]:
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")

    op.create_unique_constraint("customers_phone_key", "customers", ["phone"])
    op.create_unique_constraint("categories_name_key", "categories", ["name"])

    op.drop_index("ix_tenant_modules_tenant_id", table_name="tenant_modules")
    op.drop_table("tenant_modules")
    op.drop_table("tenants")
    enum_type = postgresql.ENUM("active", "suspended", "canceled", name="tenantstatus")
    enum_type.drop(op.get_bind(), checkfirst=False)
