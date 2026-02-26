"""add delivery_date to orders

Revision ID: 20251213a
Revises: 20251212_add_campaigns
Create Date: 2025-12-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251213a"
down_revision: Union[str, Sequence[str], None] = "20251212_add_campaigns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("delivery_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "delivery_date")
