"""remove campaign priority column

Revision ID: 20260306_remove_campaign_priority
Revises: 20260305_product_image_urls_video_position
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260306_remove_campaign_priority"
down_revision: Union[str, Sequence[str], None] = "20260305_product_image_urls_video_position"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("campaigns", "priority")


def downgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
