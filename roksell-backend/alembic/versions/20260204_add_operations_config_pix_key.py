"""add operations_config pix_key

Revision ID: 20260204_pix_key
Revises: 20260125_whatsapp_window
Create Date: 2026-02-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260204_pix_key"
down_revision = "20260125_whatsapp_window"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operations_config", sa.Column("pix_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("operations_config", "pix_key")
