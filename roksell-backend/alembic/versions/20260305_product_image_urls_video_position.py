"""add product image_urls and video_position for carousel

Revision ID: 20260305_product_image_urls_video_position
Revises: 20260305_add_additional_image_url
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260305_product_image_urls_video_position"
down_revision: Union[str, Sequence[str], None] = "20260305_add_additional_image_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image_urls", sa.JSON(), nullable=True))
    op.add_column(
        "products",
        sa.Column("video_position", sa.String(10), nullable=False, server_default="end"),
    )
    # Backfill: single image_url -> image_urls array
    op.execute("""
        UPDATE products
        SET image_urls = json_build_array(image_url)
        WHERE image_url IS NOT NULL AND image_urls IS NULL
    """)


def downgrade() -> None:
    op.drop_column("products", "video_position")
    op.drop_column("products", "image_urls")
