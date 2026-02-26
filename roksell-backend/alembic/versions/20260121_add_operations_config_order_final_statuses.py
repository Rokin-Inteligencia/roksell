"""add operations config order final statuses

Revision ID: 20260121_ops_cfg_finalstatuses
Revises: 20260121_ops_cfg_statuscolors
Create Date: 2026-01-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260121_ops_cfg_finalstatuses"
down_revision: Union[str, Sequence[str], None] = "20260121_ops_cfg_statuscolors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("operations_config", sa.Column("order_final_statuses", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("operations_config", "order_final_statuses")
