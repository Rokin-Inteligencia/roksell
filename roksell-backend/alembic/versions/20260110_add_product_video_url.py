"""add product video url

Revision ID: 20260110_add_product_video_url
Revises: 20251223_store_inventory
Create Date: 2026-01-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260110_add_product_video_url"
down_revision: Union[str, Sequence[str], None] = "20251223_store_inventory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("video_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "video_url")
