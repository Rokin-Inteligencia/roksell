"""add operations config shipping method

Revision ID: 20260116_ops_cfg_shipping_method
Revises: d9742f2626c5
Create Date: 2026-01-16 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260116_ops_cfg_shipping_method"
down_revision: Union[str, Sequence[str], None] = "d9742f2626c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("operations_config", sa.Column("shipping_method", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("operations_config", "shipping_method")
