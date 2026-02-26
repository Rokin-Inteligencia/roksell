"""add product block_sale

Revision ID: 20260111_add_product_block_sale
Revises: 20260110a, 20260111_add_tenant_stores_limit
Create Date: 2026-01-11 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260111_add_product_block_sale"
down_revision: Union[str, Sequence[str], None] = ("20260110a", "20260111_add_tenant_stores_limit")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("block_sale", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("products", "block_sale")
