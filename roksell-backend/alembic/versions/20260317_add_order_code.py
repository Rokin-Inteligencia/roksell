"""add order code (sequential per tenant)

Revision ID: 20260317_order_code
Revises: 20260312_product_code_um
Create Date: 2026-03-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260317_order_code"
down_revision: Union[str, Sequence[str], None] = "20260312_product_code_um"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("code", sa.Integer(), nullable=True),
    )

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text("""
                WITH ordered AS (
                    SELECT id, tenant_id,
                           row_number() OVER (PARTITION BY tenant_id ORDER BY created_at, id) AS rn
                    FROM orders
                )
                UPDATE orders o
                SET code = ordered.rn
                FROM ordered
                WHERE o.id = ordered.id
            """)
        )
    else:
        result = conn.execute(
            sa.text(
                "SELECT id, tenant_id, created_at FROM orders ORDER BY tenant_id, created_at, id"
            )
        )
        rows = result.fetchall()
        current_tenant: str | None = None
        next_code = 0
        for row in rows:
            id_, tenant_id, _ = row
            if tenant_id != current_tenant:
                current_tenant = tenant_id
                next_code = 1
            else:
                next_code += 1
            conn.execute(sa.text("UPDATE orders SET code = :c WHERE id = :i"), {"c": next_code, "i": id_})

    op.alter_column(
        "orders",
        "code",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("1"),
    )
    if conn.dialect.name == "postgresql":
        op.create_index(
            "uq_order_code_tenant",
            "orders",
            ["tenant_id", "code"],
            unique=True,
        )
    else:
        op.create_index(
            "uq_order_code_tenant",
            "orders",
            ["tenant_id", "code"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("uq_order_code_tenant", table_name="orders")
    op.drop_column("orders", "code")
