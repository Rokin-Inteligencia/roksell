"""remove customer plans

Revision ID: 20260210_remove_customer_plans
Revises: 20260210_add_customer_plans_and_payment_links
Create Date: 2026-02-10 15:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260210_remove_customer_plans"
down_revision = "20260210_add_customer_plans_and_payment_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("fk_customers_customer_plan_id", "customers", type_="foreignkey")
    op.drop_index("ix_customers_customer_plan_id", table_name="customers")
    op.drop_column("customers", "customer_plan_id")

    op.drop_index("ix_customer_plans_tenant_id", table_name="customer_plans")
    op.drop_table("customer_plans")


def downgrade() -> None:
    op.create_table(
        "customer_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("permissions_json", sa.Text(), nullable=True),
        sa.Column("settings_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_customer_plan_tenant_name"),
    )
    op.create_index("ix_customer_plans_tenant_id", "customer_plans", ["tenant_id"])

    op.add_column("customers", sa.Column("customer_plan_id", sa.String(length=36), nullable=True))
    op.create_index("ix_customers_customer_plan_id", "customers", ["customer_plan_id"])
    op.create_foreign_key(
        "fk_customers_customer_plan_id",
        "customers",
        "customer_plans",
        ["customer_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )
