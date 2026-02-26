"""add is_active to customers

Revision ID: 20251213b
Revises: 20251213a
Create Date: 2025-12-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251213b"
down_revision: Union[str, Sequence[str], None] = "20251213a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.alter_column("customers", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("customers", "is_active")
