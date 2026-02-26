import argparse
from typing import Iterable

from app import models
from app.db import SessionLocal
from app.phone import normalize_phone


def _iter_customers(session, tenant_id: str | None) -> Iterable[models.Customer]:
    query = session.query(models.Customer)
    if tenant_id:
        query = query.filter(models.Customer.tenant_id == tenant_id)
    return query.order_by(models.Customer.created_at.asc()).yield_per(500)


def normalize_customers(tenant_id: str | None, dry_run: bool) -> dict[str, int]:
    session = SessionLocal()
    updated = 0
    skipped = 0
    invalid = 0
    conflicts = 0
    try:
        existing_by_phone: dict[tuple[str, str], str] = {}
        for customer in _iter_customers(session, tenant_id):
            if customer.phone:
                existing_by_phone[(customer.tenant_id, customer.phone)] = customer.id

        seen_targets: set[tuple[str, str]] = set()
        for customer in _iter_customers(session, tenant_id):
            original = customer.phone or ""
            normalized = normalize_phone(original)
            if not normalized:
                invalid += 1
                continue
            key = (customer.tenant_id, normalized)
            if key in seen_targets:
                conflicts += 1
                continue
            seen_targets.add(key)
            if normalized == original:
                skipped += 1
                continue
            existing_id = existing_by_phone.get(key)
            if existing_id and existing_id != customer.id:
                conflicts += 1
                continue
            customer.phone = normalized
            existing_by_phone[key] = customer.id
            updated += 1
            if updated % 200 == 0:
                session.flush()
        if dry_run:
            session.rollback()
        else:
            session.commit()
    finally:
        session.close()
    return {
        "updated": updated,
        "skipped": skipped,
        "invalid": invalid,
        "conflicts": conflicts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normaliza telefones antigos na tabela de clientes.")
    parser.add_argument("--tenant", help="Tenant ID para filtrar (opcional).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nao aplica mudancas (apenas simula).",
    )
    args = parser.parse_args()

    result = normalize_customers(args.tenant, args.dry_run)
    mode = "SIMULACAO" if args.dry_run else "APLICADO"
    print(
        f"{mode}: atualizados={result['updated']} | "
        f"inalterados={result['skipped']} | "
        f"invalidos={result['invalid']} | "
        f"conflitos={result['conflicts']}"
    )


if __name__ == "__main__":
    main()
