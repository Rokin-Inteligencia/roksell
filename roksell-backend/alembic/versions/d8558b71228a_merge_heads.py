"""merge heads

Revision ID: d8558b71228a
Revises: 0b4c3a9d5925, 20251201_users_limit
Create Date: 2025-12-01 23:09:46.519236

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8558b71228a'
down_revision: Union[str, Sequence[str], None] = ('0b4c3a9d5925', '20251201_users_limit')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
