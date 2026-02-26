"""add config module and backfill plan/tenant access

Revision ID: 20260216_add_config_module
Revises: 20260216_add_product_masters
Create Date: 2026-02-16 20:10:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260216_add_config_module"
down_revision = "20260216_add_product_masters"
branch_labels = None
depends_on = None

MODULE_KEY = "config"


def _get_or_create_module_id(bind) -> str:
    existing_id = bind.execute(
        sa.text(
            """
            SELECT id
            FROM modules
            WHERE key = :module_key
            LIMIT 1
            """
        ),
        {"module_key": MODULE_KEY},
    ).scalar()
    if existing_id:
        bind.execute(
            sa.text(
                """
                UPDATE modules
                SET is_active = true
                WHERE id = :module_id
                """
            ),
            {"module_id": existing_id},
        )
        return str(existing_id)

    module_id = str(uuid.uuid4())
    bind.execute(
        sa.text(
            """
            INSERT INTO modules (id, key, name, description, is_active)
            VALUES (:id, :key, :name, :description, true)
            """
        ),
        {
            "id": module_id,
            "key": MODULE_KEY,
            "name": "Configuracoes",
            "description": "Acesso ao menu de configuracoes",
        },
    )
    return module_id


def upgrade() -> None:
    bind = op.get_bind()
    module_id = _get_or_create_module_id(bind)

    bind.execute(
        sa.text(
            """
            INSERT INTO plan_modules (plan_id, module_id)
            SELECT plans.id, :module_id
            FROM plans
            WHERE NOT EXISTS (
                SELECT 1
                FROM plan_modules
                WHERE plan_modules.plan_id = plans.id
                  AND plan_modules.module_id = :module_id
            )
            """
        ),
        {"module_id": module_id},
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO tenant_modules (tenant_id, module)
            SELECT tenants.id, :module_key
            FROM tenants
            WHERE NOT EXISTS (
                SELECT 1
                FROM tenant_modules
                WHERE tenant_modules.tenant_id = tenants.id
                  AND tenant_modules.module = :module_key
            )
            """
        ),
        {"module_key": MODULE_KEY},
    )


def downgrade() -> None:
    bind = op.get_bind()
    module_id = bind.execute(
        sa.text(
            """
            SELECT id
            FROM modules
            WHERE key = :module_key
            LIMIT 1
            """
        ),
        {"module_key": MODULE_KEY},
    ).scalar()

    bind.execute(
        sa.text(
            """
            DELETE FROM tenant_modules
            WHERE module = :module_key
            """
        ),
        {"module_key": MODULE_KEY},
    )

    if module_id:
        bind.execute(
            sa.text(
                """
                DELETE FROM plan_modules
                WHERE module_id = :module_id
                """
            ),
            {"module_id": module_id},
        )

    bind.execute(
        sa.text(
            """
            DELETE FROM modules
            WHERE key = :module_key
            """
        ),
        {"module_key": MODULE_KEY},
    )
