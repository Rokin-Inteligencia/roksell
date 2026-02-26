"""move payment link fields to tenant

Revision ID: 20260210_move_payment_link_to_tenant
Revises: 20260210_remove_customer_plans
Create Date: 2026-02-10 16:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260210_move_payment_link_to_tenant"
down_revision = "20260210_remove_customer_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "person_type",
            sa.Enum("individual", "company", name="customerpersontype"),
            nullable=False,
            server_default="company",
        ),
    )
    op.add_column("tenants", sa.Column("document", sa.String(length=32), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("payment_link_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("tenants", sa.Column("payment_link_config", sa.Text(), nullable=True))

    op.drop_column("customers", "payment_link_config")
    op.drop_column("customers", "payment_link_enabled")
    op.drop_column("customers", "document")
    op.drop_column("customers", "person_type")


def downgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "person_type",
            sa.Enum("individual", "company", name="customerpersontype"),
            nullable=False,
            server_default="individual",
        ),
    )
    op.add_column("customers", sa.Column("document", sa.String(length=32), nullable=True))
    op.add_column(
        "customers",
        sa.Column("payment_link_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("customers", sa.Column("payment_link_config", sa.Text(), nullable=True))

    op.drop_column("tenants", "payment_link_config")
    op.drop_column("tenants", "payment_link_enabled")
    op.drop_column("tenants", "document")
    op.drop_column("tenants", "person_type")
