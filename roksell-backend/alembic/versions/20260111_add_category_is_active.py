"""add category is_active flag

Revision ID: 20260111_add_category_is_active
Revises: 20260110_add_product_is_custom
Create Date: 2026-01-11 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260111_add_category_is_active"
down_revision: Union[str, Sequence[str], None] = "20260110_add_product_is_custom"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.alter_column("categories", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("categories", "is_active")
