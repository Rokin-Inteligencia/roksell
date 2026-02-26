"""replace single-session fields with multi-session table

Revision ID: 20260219_user_sessions_multi_login
Revises: 20260219_add_user_session_control
Create Date: 2026-02-19 12:35:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260219_user_sessions_multi_login"
down_revision = "20260219_add_user_session_control"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("max_active_sessions", sa.Integer(), nullable=False, server_default="3"),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_tenant_id", "user_sessions", ["tenant_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.execute(
        sa.text(
            """
            INSERT INTO user_sessions (
                id,
                user_id,
                tenant_id,
                created_at,
                expires_at,
                revoked_at,
                revoked_reason
            )
            SELECT
                users.active_session_id,
                users.id,
                users.tenant_id,
                COALESCE(users.session_started_at, now()),
                users.session_expires_at,
                NULL,
                NULL
            FROM users
            WHERE users.active_session_id IS NOT NULL
              AND users.session_expires_at IS NOT NULL
            """
        )
    )

    op.drop_column("users", "session_expires_at")
    op.drop_column("users", "session_started_at")
    op.drop_column("users", "active_session_id")


def downgrade() -> None:
    op.add_column("users", sa.Column("active_session_id", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("session_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE users
            SET
                active_session_id = latest.id,
                session_started_at = latest.created_at,
                session_expires_at = latest.expires_at
            FROM (
                SELECT DISTINCT ON (user_id)
                    user_id,
                    id,
                    created_at,
                    expires_at
                FROM user_sessions
                WHERE revoked_at IS NULL
                ORDER BY user_id, created_at DESC
            ) AS latest
            WHERE users.id = latest.user_id
            """
        )
    )

    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_tenant_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_column("users", "max_active_sessions")
