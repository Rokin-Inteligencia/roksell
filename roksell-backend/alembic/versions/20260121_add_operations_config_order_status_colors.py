"""add operations config order status colors

Revision ID: 20260121_ops_cfg_statuscolors
Revises: 20260121_ops_cfg_cancelclr
Create Date: 2026-01-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260121_ops_cfg_statuscolors"
down_revision: Union[str, Sequence[str], None] = "20260121_ops_cfg_cancelclr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("operations_config", sa.Column("order_status_colors", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("operations_config", "order_status_colors")
