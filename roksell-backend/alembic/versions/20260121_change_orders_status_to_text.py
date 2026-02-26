"""change orders.status to text

Revision ID: 20260121_orders_status_text
Revises: 20260121_ops_cfg_order_statuses
Create Date: 2026-01-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260121_orders_status_text"
down_revision: Union[str, Sequence[str], None] = "20260121_ops_cfg_order_statuses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE orders ALTER COLUMN status TYPE text USING status::text")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE orders ALTER COLUMN status TYPE orderstatus USING status::orderstatus")
