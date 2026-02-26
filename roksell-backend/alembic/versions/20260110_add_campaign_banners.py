"""add campaign banners

Revision ID: 20260110a
Revises: 20251213a
Create Date: 2026-01-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260110a"
down_revision: Union[str, Sequence[str], None] = "20251213a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("banner_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("campaigns", sa.Column("banner_position", sa.String(length=16), nullable=True))
    op.add_column(
        "campaigns",
        sa.Column("banner_popup", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("campaigns", sa.Column("banner_image_url", sa.Text(), nullable=True))
    op.add_column("campaigns", sa.Column("banner_link_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("campaigns", "banner_link_url")
    op.drop_column("campaigns", "banner_image_url")
    op.drop_column("campaigns", "banner_popup")
    op.drop_column("campaigns", "banner_position")
    op.drop_column("campaigns", "banner_enabled")
