"""add auth tables

Revision ID: 4e23b1664d6e
Revises: 9a2f9fc2b50b
Create Date: 2025-11-15 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4e23b1664d6e"
down_revision: Union[str, Sequence[str], None] = "9a2f9fc2b50b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "manager", "operator", name="userrole"),
            nullable=False,
            server_default="owner",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_user_email_tenant"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")
    sa.Enum("owner", "manager", "operator", name="userrole").drop(op.get_bind(), checkfirst=False)
