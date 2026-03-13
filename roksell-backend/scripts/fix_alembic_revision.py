"""
One-off: corrige alembic_version quando o banco tem uma revisão que não existe mais no código
(ex.: 20260306_provider_order_id). Define para 20260306_banner_display_order para permitir
rodar alembic upgrade head e aplicar 20260312_product_code_um.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.db import settings

def main():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        r = conn.execute(text("SELECT version_num FROM alembic_version"))
        row = r.fetchone()
        if not row:
            print("alembic_version vazia.")
            return 1
        current = row[0]
        print(f"Revisão atual no banco: {current}")
        if current == "20260306_provider_order_id":
            conn.execute(text("UPDATE alembic_version SET version_num = '20260306_banner_display_order' WHERE version_num = '20260306_provider_order_id'"))
            conn.commit()
            print("Atualizado para 20260306_banner_display_order. Rode: alembic upgrade head")
            return 0
        print("Nada a alterar.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
