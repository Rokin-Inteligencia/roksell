"""add operations config canceled status color

Revision ID: 20260121_ops_cfg_cancelclr
Revises: 20260121_orders_status_text
Create Date: 2026-01-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260121_ops_cfg_cancelclr"
down_revision: Union[str, Sequence[str], None] = "20260121_orders_status_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("operations_config", sa.Column("order_status_canceled_color", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("operations_config", "order_status_canceled_color")
