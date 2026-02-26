"""add product is_custom flag

Revision ID: 20260110_add_product_is_custom
Revises: 20260110_add_product_video_url
Create Date: 2026-01-10 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260110_add_product_is_custom"
down_revision: Union[str, Sequence[str], None] = "20260110_add_product_video_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("products", "is_custom", server_default=None)


def downgrade() -> None:
    op.drop_column("products", "is_custom")
