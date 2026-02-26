"""add operations config payment methods

Revision ID: d9742f2626c5
Revises: 421bdfd176df
Create Date: 2026-01-16 21:07:15.036792

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9742f2626c5'
down_revision: Union[str, Sequence[str], None] = '421bdfd176df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("operations_config", sa.Column("payment_methods", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("operations_config", "payment_methods")
