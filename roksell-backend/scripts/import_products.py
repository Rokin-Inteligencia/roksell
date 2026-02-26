import csv
import sys
import uuid
from datetime import datetime
from pathlib import Path

from app import models
from app.db import SessionLocal
from app.tenancy import legacy_tenant_id


def parse_dt(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace(" ", "T").replace("Z", "+00:00"))
    except Exception:
        return None


def import_products(csv_path: Path, tenant_id: str):
    session = SessionLocal()

    categories = {
        c.id: True
        for c in session.query(models.Category.id)
        .filter(models.Category.tenant_id == tenant_id)
        .all()
    }

    inserted = updated = skipped = 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id = row.get("id") or str(uuid.uuid4())
            name = (row.get("nome") or "").strip()
            if not name:
                skipped += 1
                continue

            category_id = row.get("categoria_id") or None
            if category_id and category_id not in categories:
                category_id = None

            fields = dict(
                name=name,
                description=row.get("descricao"),
                price_cents=int(row.get("preco_centavos") or 0),
                is_active=str(row.get("status_ativo")).lower() in ("true", "1", "yes", "sim"),
                image_url=row.get("foto_url"),
                category_id=category_id,
                display_order=int(row.get("ordem") or 0),
                tags=row.get("tags"),
            )

            existing = (
                session.query(models.Product)
                .filter(models.Product.id == product_id, models.Product.tenant_id == tenant_id)
                .first()
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                product = models.Product(id=product_id, tenant_id=tenant_id, **fields)
                created_at = parse_dt(row.get("created_at"))
                if created_at:
                    product.created_at = created_at
                session.add(product)
                inserted += 1

    session.commit()
    session.close()
    return dict(inserted=inserted, updated=updated, skipped=skipped)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m scripts.import_products <produtos.csv>")
        sys.exit(1)

    csv_path = Path(sys.argv[1]).expanduser().resolve()
    tenant_id = legacy_tenant_id()
    result = import_products(csv_path, tenant_id)
    print("Importação concluída:", result)
