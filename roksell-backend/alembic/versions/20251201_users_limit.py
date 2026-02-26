"""add users_limit to tenants"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251201_users_limit"
down_revision = "9a2f9fc2b50b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("users_limit", sa.Integer(), nullable=False, server_default="5"),
    )
    op.alter_column("tenants", "users_limit", server_default=None)


def downgrade() -> None:
    op.drop_column("tenants", "users_limit")
