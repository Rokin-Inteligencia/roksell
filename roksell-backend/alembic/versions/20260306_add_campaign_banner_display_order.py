"""add campaign banner_display_order

Revision ID: 20260306_banner_display_order
Revises: 20260306_remove_campaign_priority
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260306_banner_display_order"
down_revision: Union[str, Sequence[str], None] = "20260306_remove_campaign_priority"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("banner_display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "banner_display_order")
