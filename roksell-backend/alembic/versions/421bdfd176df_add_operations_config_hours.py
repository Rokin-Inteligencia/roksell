"""add operations config hours

Revision ID: 421bdfd176df
Revises: b0cb088ab185
Create Date: 2026-01-16 07:51:33.575068

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '421bdfd176df'
down_revision: Union[str, Sequence[str], None] = 'b0cb088ab185'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("operations_config", sa.Column("operating_hours", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("operations_config", "operating_hours")
