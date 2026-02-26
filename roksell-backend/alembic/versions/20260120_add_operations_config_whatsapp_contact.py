"""add operations config whatsapp contact phone

Revision ID: 20260120_ops_cfg_whatsapp
Revises: 20260116_whatsapp_logs
Create Date: 2026-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260120_ops_cfg_whatsapp"
down_revision: Union[str, Sequence[str], None] = "20260116_whatsapp_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("operations_config", sa.Column("whatsapp_contact_phone", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("operations_config", "whatsapp_contact_phone")
