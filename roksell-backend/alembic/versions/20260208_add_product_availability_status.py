"""add product availability_status

Revision ID: 20260208_add_product_availability_status
Revises: 20260207_add_wa_media
Create Date: 2026-02-08 10:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260208_add_product_availability_status"
down_revision = "20260207_add_wa_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("availability_status", sa.String(length=24), nullable=False, server_default=sa.text("'available'")),
    )
    op.execute("UPDATE products SET availability_status = 'order' WHERE block_sale = true")


def downgrade() -> None:
    op.drop_column("products", "availability_status")
