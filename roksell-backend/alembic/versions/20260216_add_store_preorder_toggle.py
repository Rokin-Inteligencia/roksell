"""add per-store preorder toggle when closed

Revision ID: 20260216_add_store_preorder_toggle
Revises: 20260216_add_config_module
Create Date: 2026-02-16 21:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260216_add_store_preorder_toggle"
down_revision = "20260216_add_config_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stores",
        sa.Column(
            "allow_preorder_when_closed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("stores", "allow_preorder_when_closed")
