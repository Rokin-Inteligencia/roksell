"""add product code (6 digits per tenant/store) and unit_of_measure

Revision ID: 20260312_product_code_um
Revises: 20260306_banner_display_order
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260312_product_code_um"
down_revision: Union[str, Sequence[str], None] = "20260306_banner_display_order"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("code", sa.Integer(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("unit_of_measure", sa.String(length=24), nullable=True),
    )

    # Backfill: assign sequential code per (tenant_id, store_id)
    # Use raw SQL for portability; PostgreSQL syntax for row_number per group
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text("""
                WITH ordered AS (
                    SELECT id, tenant_id, store_id,
                           row_number() OVER (
                               PARTITION BY tenant_id, COALESCE(store_id::text, '')
                               ORDER BY created_at, id
                           ) AS rn
                    FROM products
                )
                UPDATE products p
                SET code = ordered.rn
                FROM ordered
                WHERE p.id = ordered.id
            """)
        )
    else:
        # SQLite / other: single pass per (tenant_id, store_id)
        result = conn.execute(sa.text(
            "SELECT id, tenant_id, store_id, created_at FROM products ORDER BY tenant_id, COALESCE(store_id, ''), created_at, id"
        ))
        rows = result.fetchall()
        current_key: tuple[str, str] | None = None
        next_code = 0
        for row in rows:
            id_, tenant_id, store_id, _ = row
            key = (tenant_id or "", store_id or "")
            if key != current_key:
                current_key = key
                next_code = 1
            else:
                next_code += 1
            conn.execute(sa.text("UPDATE products SET code = :c WHERE id = :i"), {"c": next_code, "i": id_})

    op.alter_column(
        "products",
        "code",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("1"),
    )
    # Unique code per (tenant_id, store_id); NULL store_id treated as one group
    if conn.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_product_code_tenant_store ON products (tenant_id, COALESCE(store_id::text, ''), code)"
            )
        )
    else:
        op.create_index(
            "uq_product_code_tenant_store",
            "products",
            ["tenant_id", "store_id", "code"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS uq_product_code_tenant_store"))
    else:
        op.drop_index("uq_product_code_tenant_store", table_name="products")
    op.drop_column("products", "unit_of_measure")
    op.drop_column("products", "code")
