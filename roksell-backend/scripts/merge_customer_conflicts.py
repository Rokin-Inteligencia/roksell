import argparse
import csv
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func

from app import models
from app.db import SessionLocal
from app.phone import normalize_phone


def _load_customers(session, tenant_id: str | None):
    query = session.query(models.Customer)
    if tenant_id:
        query = query.filter(models.Customer.tenant_id == tenant_id)
    return query.order_by(models.Customer.created_at.asc()).all()


def _orders_count_map(session, customer_ids: list[str]) -> dict[str, int]:
    if not customer_ids:
        return {}
    rows = (
        session.query(models.Order.customer_id, func.count(models.Order.id))
        .filter(models.Order.customer_id.in_(customer_ids))
        .group_by(models.Order.customer_id)
        .all()
    )
    return {cid: int(count or 0) for cid, count in rows}


def merge_conflicts(tenant_id: str | None, dry_run: bool) -> dict[str, int]:
    session = SessionLocal()
    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "customer_merge_report.csv"

    merged_groups = 0
    merged_customers = 0
    updated_orders = 0
    updated_addresses = 0

    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "tenant_id",
                "normalized_phone",
                "keeper_id",
                "keeper_name_before",
                "keeper_name_after",
                "merged_ids",
                "orders_moved",
                "addresses_moved",
            ]
        )

        try:
            customers = _load_customers(session, tenant_id)
            groups: dict[tuple[str, str], list[models.Customer]] = defaultdict(list)
            for customer in customers:
                normalized = normalize_phone(customer.phone or "")
                if not normalized:
                    continue
                groups[(customer.tenant_id, normalized)].append(customer)

            for (tenant_key, normalized_phone), items in groups.items():
                if len(items) < 2:
                    continue

                ids = [c.id for c in items]
                order_counts = _orders_count_map(session, ids)

                def sort_key(cust: models.Customer):
                    return (
                        order_counts.get(cust.id, 0),
                        cust.created_at or 0,
                    )

                keeper = max(items, key=sort_key)
                keeper_name_before = keeper.name
                merged_ids: list[str] = []
                moved_orders = 0
                moved_addresses = 0

                for other in items:
                    if other.id == keeper.id:
                        continue
                    merged_ids.append(other.id)
                    moved_orders += session.query(models.Order).filter(
                        models.Order.customer_id == other.id
                    ).update({models.Order.customer_id: keeper.id}, synchronize_session=False)
                    moved_addresses += session.query(models.CustomerAddress).filter(
                        models.CustomerAddress.customer_id == other.id
                    ).update({models.CustomerAddress.customer_id: keeper.id}, synchronize_session=False)

                    if other.name and (not keeper.name or len(other.name.strip()) > len(keeper.name.strip())):
                        keeper.name = other.name
                    if not keeper.birthday and other.birthday:
                        keeper.birthday = other.birthday
                    if other.is_active and not keeper.is_active:
                        keeper.is_active = True
                    session.delete(other)

                session.flush()
                if keeper.phone != normalized_phone:
                    keeper.phone = normalized_phone

                merged_groups += 1
                merged_customers += len(merged_ids)
                updated_orders += moved_orders
                updated_addresses += moved_addresses
                writer.writerow(
                    [
                        tenant_key,
                        normalized_phone,
                        keeper.id,
                        keeper_name_before,
                        keeper.name,
                        ";".join(merged_ids),
                        moved_orders,
                        moved_addresses,
                    ]
                )

            if dry_run:
                session.rollback()
            else:
                session.commit()
        finally:
            session.close()

    return {
        "merged_groups": merged_groups,
        "merged_customers": merged_customers,
        "updated_orders": updated_orders,
        "updated_addresses": updated_addresses,
        "report_path": str(report_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mescla clientes duplicados por telefone normalizado.")
    parser.add_argument("--tenant", help="Tenant ID para filtrar (opcional).")
    parser.add_argument("--dry-run", action="store_true", help="Simula a mesclagem sem gravar.")
    args = parser.parse_args()

    result = merge_conflicts(args.tenant, args.dry_run)
    mode = "SIMULACAO" if args.dry_run else "APLICADO"
    print(
        f"{mode}: grupos={result['merged_groups']} | "
        f"clientes_mesclados={result['merged_customers']} | "
        f"orders_movidos={result['updated_orders']} | "
        f"enderecos_movidos={result['updated_addresses']}"
    )
    print(f"Report: {result['report_path']}")


if __name__ == "__main__":
    main()
