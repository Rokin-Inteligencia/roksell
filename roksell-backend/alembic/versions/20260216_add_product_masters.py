"""add product masters and link products to master identity

Revision ID: 20260216_add_product_masters
Revises: 20260215_groups_store_catalog_scope
Create Date: 2026-02-16 18:30:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260216_add_product_masters"
down_revision = "20260215_groups_store_catalog_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_masters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name_canonical", sa.String(), nullable=False),
        sa.Column("sku_global", sa.String(length=64), nullable=True),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_masters_tenant_id", "product_masters", ["tenant_id"])
    op.create_index("ix_product_masters_sku_global", "product_masters", ["sku_global"])

    op.add_column("products", sa.Column("product_master_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_products_product_master",
        "products",
        "product_masters",
        ["product_master_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_products_product_master_id", "products", ["product_master_id"])

    bind = op.get_bind()
    product_rows = bind.execute(
        sa.text(
            """
            SELECT id, tenant_id, name
            FROM products
            ORDER BY tenant_id, id
            """
        )
    ).mappings().all()

    for row in product_rows:
        master_id = str(uuid.uuid4())
        name = (row["name"] or "").strip() or "Produto"
        bind.execute(
            sa.text(
                """
                INSERT INTO product_masters (id, tenant_id, name_canonical, sku_global, is_shared)
                VALUES (:id, :tenant_id, :name_canonical, :sku_global, :is_shared)
                """
            ),
            {
                "id": master_id,
                "tenant_id": row["tenant_id"],
                "name_canonical": name,
                "sku_global": None,
                "is_shared": False,
            },
        )
        bind.execute(
            sa.text(
                """
                UPDATE products
                SET product_master_id = :product_master_id
                WHERE id = :product_id
                """
            ),
            {
                "product_master_id": master_id,
                "product_id": row["id"],
            },
        )

    op.alter_column("products", "product_master_id", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_products_product_master_id", table_name="products")
    op.drop_constraint("fk_products_product_master", "products", type_="foreignkey")
    op.drop_column("products", "product_master_id")

    op.drop_index("ix_product_masters_sku_global", table_name="product_masters")
    op.drop_index("ix_product_masters_tenant_id", table_name="product_masters")
    op.drop_table("product_masters")
