"""merge heads

Revision ID: b0cb088ab185
Revises: 20260111_add_product_block_sale, 20260113_ops_cfg_cover
Create Date: 2026-01-16 07:39:28.145815

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0cb088ab185'
down_revision: Union[str, Sequence[str], None] = ('20260111_add_product_block_sale', '20260113_ops_cfg_cover')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
