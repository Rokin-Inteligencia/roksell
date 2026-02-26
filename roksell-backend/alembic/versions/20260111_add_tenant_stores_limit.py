"""add tenant stores_limit

Revision ID: 20260111_add_tenant_stores_limit
Revises: 20260111_add_category_is_active
Create Date: 2026-01-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260111_add_tenant_stores_limit"
down_revision: Union[str, Sequence[str], None] = "20260111_add_category_is_active"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("stores_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "stores_limit")
