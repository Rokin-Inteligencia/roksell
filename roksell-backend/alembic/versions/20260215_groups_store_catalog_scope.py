"""add user groups and store scoped catalog

Revision ID: 20260215_groups_store_catalog_scope
Revises: 20260210_move_payment_link_to_tenant
Create Date: 2026-02-15 11:00:00
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260215_groups_store_catalog_scope"
down_revision = "20260210_move_payment_link_to_tenant"
branch_labels = None
depends_on = None


def _normalize_store_slug(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "loja"


def upgrade() -> None:
    op.add_column("stores", sa.Column("slug", sa.String(), nullable=True))

    op.add_column("categories", sa.Column("store_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_categories_store",
        "categories",
        "stores",
        ["store_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_categories_store_id", "categories", ["store_id"])

    op.add_column("products", sa.Column("store_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_products_store",
        "products",
        "stores",
        ["store_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_products_store_id", "products", ["store_id"])

    op.add_column("customers", sa.Column("origin_store_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_customers_origin_store",
        "customers",
        "stores",
        ["origin_store_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "user_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("permissions_json", sa.Text(), nullable=True),
        sa.Column("store_ids_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_user_group_name_tenant"),
    )
    op.create_index("ix_user_groups_tenant_id", "user_groups", ["tenant_id"])

    op.add_column("users", sa.Column("group_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_users_group",
        "users",
        "user_groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_group_id", "users", ["group_id"])

    bind = op.get_bind()

    store_rows = bind.execute(
        sa.text(
            """
            SELECT id, tenant_id, name
            FROM stores
            ORDER BY tenant_id, name, id
            """
        )
    ).mappings().all()

    slug_counts: dict[tuple[str, str], int] = {}
    tenant_default_store: dict[str, str] = {}
    tenant_store_ids: dict[str, list[str]] = {}
    for row in store_rows:
        tenant_id = row["tenant_id"]
        store_id = row["id"]
        base_slug = _normalize_store_slug(row["name"] or "")
        key = (tenant_id, base_slug)
        next_count = slug_counts.get(key, 0) + 1
        slug_counts[key] = next_count
        slug = base_slug if next_count == 1 else f"{base_slug}-{next_count}"
        bind.execute(
            sa.text("UPDATE stores SET slug = :slug WHERE id = :store_id"),
            {"slug": slug, "store_id": store_id},
        )
        if tenant_id not in tenant_default_store:
            tenant_default_store[tenant_id] = store_id
        tenant_store_ids.setdefault(tenant_id, []).append(store_id)

    bind.execute(
        sa.text(
            """
            UPDATE categories c
            SET store_id = s.id
            FROM stores s
            WHERE c.store_id IS NULL
              AND s.tenant_id = c.tenant_id
              AND s.id = (
                  SELECT s2.id
                  FROM stores s2
                  WHERE s2.tenant_id = c.tenant_id
                  ORDER BY s2.name ASC, s2.id ASC
                  LIMIT 1
              )
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE products p
            SET store_id = c.store_id
            FROM categories c
            WHERE p.category_id = c.id
              AND p.store_id IS NULL
              AND c.store_id IS NOT NULL
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE products p
            SET store_id = s.id
            FROM stores s
            WHERE p.store_id IS NULL
              AND s.tenant_id = p.tenant_id
              AND s.id = (
                  SELECT s2.id
                  FROM stores s2
                  WHERE s2.tenant_id = p.tenant_id
                  ORDER BY s2.name ASC, s2.id ASC
                  LIMIT 1
              )
            """
        )
    )

    tenant_rows = bind.execute(sa.text("SELECT id FROM tenants ORDER BY id")).mappings().all()
    for tenant_row in tenant_rows:
        tenant_id = tenant_row["id"]
        group_id = str(uuid.uuid4())
        module_rows = bind.execute(
            sa.text(
                """
                SELECT module
                FROM tenant_modules
                WHERE tenant_id = :tenant_id
                ORDER BY module ASC
                """
            ),
            {"tenant_id": tenant_id},
        ).mappings().all()
        permissions = [row["module"] for row in module_rows]
        store_ids = tenant_store_ids.get(tenant_id, [])
        bind.execute(
            sa.text(
                """
                INSERT INTO user_groups (id, tenant_id, name, permissions_json, store_ids_json, is_active)
                VALUES (:id, :tenant_id, :name, :permissions_json, :store_ids_json, :is_active)
                """
            ),
            {
                "id": group_id,
                "tenant_id": tenant_id,
                "name": "Administradores",
                "permissions_json": json.dumps(permissions) if permissions else None,
                "store_ids_json": json.dumps(store_ids) if store_ids else None,
                "is_active": True,
            },
        )
        bind.execute(
            sa.text(
                """
                UPDATE users
                SET group_id = :group_id
                WHERE tenant_id = :tenant_id
                  AND group_id IS NULL
                """
            ),
            {"group_id": group_id, "tenant_id": tenant_id},
        )

    op.alter_column("stores", "slug", nullable=False)
    op.create_unique_constraint("uq_store_slug_tenant", "stores", ["tenant_id", "slug"])

    op.drop_constraint("uq_category_name_tenant", "categories", type_="unique")
    op.create_unique_constraint(
        "uq_category_name_store_tenant",
        "categories",
        ["tenant_id", "store_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_category_name_store_tenant", "categories", type_="unique")
    op.create_unique_constraint("uq_category_name_tenant", "categories", ["tenant_id", "name"])

    op.drop_constraint("uq_store_slug_tenant", "stores", type_="unique")
    op.drop_column("stores", "slug")

    op.drop_constraint("fk_users_group", "users", type_="foreignkey")
    op.drop_index("ix_users_group_id", table_name="users")
    op.drop_column("users", "group_id")

    op.drop_index("ix_user_groups_tenant_id", table_name="user_groups")
    op.drop_table("user_groups")

    op.drop_constraint("fk_customers_origin_store", "customers", type_="foreignkey")
    op.drop_column("customers", "origin_store_id")

    op.drop_constraint("fk_products_store", "products", type_="foreignkey")
    op.drop_index("ix_products_store_id", table_name="products")
    op.drop_column("products", "store_id")

    op.drop_constraint("fk_categories_store", "categories", type_="foreignkey")
    op.drop_index("ix_categories_store_id", table_name="categories")
    op.drop_column("categories", "store_id")
