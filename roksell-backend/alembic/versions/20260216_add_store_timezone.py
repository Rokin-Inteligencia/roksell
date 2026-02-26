"""add timezone to stores

Revision ID: 20260216_add_store_timezone
Revises: 20260216_add_store_preorder_toggle
Create Date: 2026-02-16 23:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260216_add_store_timezone"
down_revision = "20260216_add_store_preorder_toggle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stores",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="America/Sao_Paulo",
        ),
    )


def downgrade() -> None:
    op.drop_column("stores", "timezone")

