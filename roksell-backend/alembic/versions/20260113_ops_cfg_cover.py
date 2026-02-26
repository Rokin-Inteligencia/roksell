"""add operations_config cover image url

Revision ID: 20260113_ops_cfg_cover
Revises: 20260111_add_tenant_stores_limit
Create Date: 2026-01-13 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260113_ops_cfg_cover"
down_revision: Union[str, Sequence[str], None] = "20260111_add_tenant_stores_limit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("operations_config", sa.Column("cover_image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("operations_config", "cover_image_url")
