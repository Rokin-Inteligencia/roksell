"""add user session control fields

Revision ID: 20260219_add_user_session_control
Revises: 20260218_add_tenant_registration_fields
Create Date: 2026-02-19 10:40:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260219_add_user_session_control"
down_revision = "20260218_add_tenant_registration_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("active_session_id", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("session_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "session_expires_at")
    op.drop_column("users", "session_started_at")
    op.drop_column("users", "active_session_id")
