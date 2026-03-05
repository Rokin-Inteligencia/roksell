"""add image_url to additionals

Revision ID: 20260305_add_additional_image_url
Revises: 20260219_user_sessions_multi_login
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260305_add_additional_image_url"
down_revision: Union[str, Sequence[str], None] = "20260219_user_sessions_multi_login"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("additionals", sa.Column("image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("additionals", "image_url")
