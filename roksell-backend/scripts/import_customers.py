import csv
import sys
import uuid
from datetime import datetime
from pathlib import Path

from app import models
from app.db import SessionLocal
from app.tenancy import legacy_tenant_id


def clean_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits or None


def parse_date(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace(" ", "T").replace("Z", "+00:00"))
    except Exception:
        return None


def import_customers(csv_path: Path, tenant_id: str):
    session = SessionLocal()
    inserted = 0
    updated = 0
    skipped = 0
    seen_in_batch: set[str] = set()

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("nome") or "").strip()
            phone = clean_phone(row.get("telefone"))
            if not name or not phone:
                skipped += 1
                continue
            if phone in seen_in_batch:
                skipped += 1
                continue

            existing = (
                session.query(models.Customer)
                .filter(
                    models.Customer.tenant_id == tenant_id,
                    models.Customer.phone == phone,
                )
                .first()
            )
            seen_in_batch.add(phone)

            birthday = parse_date(row.get("aniversario"))
            created_at = parse_date(row.get("created_at"))
            updated_at = parse_date(row.get("updated_at"))

            if existing:
                existing.name = name
                existing.birthday = birthday
                if updated_at:
                    existing.updated_at = updated_at
                updated += 1
                continue

            customer = models.Customer(
                id=row.get("id") or str(uuid.uuid4()),
                tenant_id=tenant_id,
                name=name,
                phone=phone,
                birthday=birthday,
            )
            if created_at:
                customer.created_at = created_at
            if updated_at:
                customer.updated_at = updated_at
            session.add(customer)
            inserted += 1

    session.commit()
    session.close()
    return inserted, updated, skipped


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m scripts.import_customers <caminho_csv>")
        sys.exit(1)

    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.exists():
        print(f"Arquivo não encontrado: {path}")
        sys.exit(1)

    tenant_id = legacy_tenant_id()
    ins, upd, skip = import_customers(path, tenant_id)
    print(f"Importação concluída. Inseridos: {ins}, Atualizados: {upd}, Ignorados: {skip}")
