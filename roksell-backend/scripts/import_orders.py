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


ORDER_STATUS_MAP = {
    "recebido": models.OrderStatus.received,
    "preparando": models.OrderStatus.preparing,
    "pronto": models.OrderStatus.ready,
    "a_caminho": models.OrderStatus.on_route,
    "a caminho": models.OrderStatus.on_route,
    "entregue": models.OrderStatus.delivered,
    "concluido": models.OrderStatus.completed,
    "concluído": models.OrderStatus.completed,
    "cancelado": models.OrderStatus.canceled,
}

PAYMENT_METHOD_MAP = {
    "pix": models.PaymentMethod.pix,
    "dinheiro": models.PaymentMethod.cash,
    "cash": models.PaymentMethod.cash,
}

PAYMENT_STATUS_MAP = {
    "pendente": models.PaymentStatus.pending,
    "confirmado": models.PaymentStatus.confirmed,
    "canceled": models.PaymentStatus.canceled,
    "cancelado": models.PaymentStatus.canceled,
}


def import_orders(orders_csv: Path, items_csv: Path, payments_csv: Path, tenant_id: str):
    session = SessionLocal()

    customers = {
        c.id: True
        for c in session.query(models.Customer.id)
        .filter(models.Customer.tenant_id == tenant_id)
        .all()
    }
    addresses = {
        a.id: True
        for a in session.query(models.CustomerAddress.id)
        .filter(models.CustomerAddress.tenant_id == tenant_id)
        .all()
    }
    products = {
        p.id: True
        for p in session.query(models.Product.id)
        .filter(models.Product.tenant_id == tenant_id)
        .all()
    }

    inserted_orders = updated_orders = skipped_orders = 0
    with orders_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            order_id = row.get("id") or str(uuid.uuid4())
            customer_id = row.get("cliente_id")
            if not customer_id or customer_id not in customers:
                skipped_orders += 1
                continue

            address_id = row.get("endereco_id")
            if address_id not in addresses:
                address_id = None

            status_raw = (row.get("status") or "").strip().lower()
            status = ORDER_STATUS_MAP.get(status_raw, models.OrderStatus.received)

            existing = (
                session.query(models.Order)
                .filter(models.Order.id == order_id, models.Order.tenant_id == tenant_id)
                .first()
            )

            fields = dict(
                customer_id=customer_id,
                address_id=address_id,
                subtotal_cents=int(row.get("subtotal_centavos") or 0),
                shipping_cents=int(row.get("frete_centavos") or 0),
                discount_cents=int(row.get("desconto_centavos") or 0),
                total_cents=int(row.get("total_centavos") or 0),
                channel=row.get("canal") or "web",
                status=status,
                delivery_window_start=parse_dt(row.get("janela_entrega_inicio")),
                delivery_window_end=parse_dt(row.get("janela_entrega_fim")),
                notes=row.get("observacao"),
            )

            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                updated_orders += 1
            else:
                order = models.Order(
                    id=order_id,
                    tenant_id=tenant_id,
                    **fields,
                )
                created_at = parse_dt(row.get("created_at"))
                if created_at:
                    order.created_at = created_at
                session.add(order)
                inserted_orders += 1

    session.commit()

    inserted_items = skipped_items = 0
    with items_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            order_id = row.get("pedido_id")
            product_id = row.get("produto_id")
            if not order_id or not product_id:
                skipped_items += 1
                continue
            order_exists = (
                session.query(models.Order.id)
                .filter(models.Order.id == order_id, models.Order.tenant_id == tenant_id)
                .first()
            )
            if not order_exists:
                skipped_items += 1
                continue
            if product_id not in products:
                skipped_items += 1
                continue

            existing = (
                session.query(models.OrderItem)
                .filter(
                    models.OrderItem.id == (row.get("id") or ""),
                    models.OrderItem.tenant_id == tenant_id,
                )
                .first()
            )

            if existing:
                existing.product_id = product_id
                existing.quantity = int(row.get("qtd") or 0)
                existing.unit_price_cents = int(row.get("preco_unit_centavos") or 0)
                existing.notes = row.get("observacao")
            else:
                session.add(
                    models.OrderItem(
                        id=row.get("id") or str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        order_id=order_id,
                        product_id=product_id,
                        quantity=int(row.get("qtd") or 0),
                        unit_price_cents=int(row.get("preco_unit_centavos") or 0),
                        notes=row.get("observacao"),
                    )
                )
                inserted_items += 1

    session.commit()

    inserted_payments = skipped_payments = 0
    with payments_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            order_id = row.get("pedido_id")
            if not order_id:
                skipped_payments += 1
                continue
            order_exists = (
                session.query(models.Order.id)
                .filter(models.Order.id == order_id, models.Order.tenant_id == tenant_id)
                .first()
            )
            if not order_exists:
                skipped_payments += 1
                continue

            method_raw = (row.get("metodo") or "").strip().lower()
            status_raw = (row.get("status") or "").strip().lower()
            method = PAYMENT_METHOD_MAP.get(method_raw, models.PaymentMethod.cash)
            status = PAYMENT_STATUS_MAP.get(status_raw, models.PaymentStatus.pending)

            existing = (
                session.query(models.Payment)
                .filter(models.Payment.order_id == order_id, models.Payment.tenant_id == tenant_id)
                .first()
            )
            created_at = parse_dt(row.get("created_at"))
            confirmed_at = parse_dt(row.get("confirmed_at"))

            if existing:
                existing.method = method
                existing.status = status
                existing.amount_cents = int(row.get("valor_centavos") or 0)
                existing.txid = row.get("txid")
                if created_at:
                    existing.created_at = created_at
                if confirmed_at:
                    existing.confirmed_at = confirmed_at
            else:
                payment = models.Payment(
                    id=row.get("id") or str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    order_id=order_id,
                    method=method,
                    status=status,
                    amount_cents=int(row.get("valor_centavos") or 0),
                    txid=row.get("txid"),
                )
                if created_at:
                    payment.created_at = created_at
                if confirmed_at:
                    payment.confirmed_at = confirmed_at
                session.add(payment)
                inserted_payments += 1

    session.commit()
    session.close()
    return {
        "orders": dict(inserted=inserted_orders, updated=updated_orders, skipped=skipped_orders),
        "items": dict(inserted=inserted_items, skipped=skipped_items),
        "payments": dict(inserted=inserted_payments, skipped=skipped_payments),
    }


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python -m scripts.import_orders <pedidos.csv> <pedido_itens.csv> <pagamentos.csv>")
        sys.exit(1)

    orders_csv = Path(sys.argv[1]).expanduser().resolve()
    items_csv = Path(sys.argv[2]).expanduser().resolve()
    payments_csv = Path(sys.argv[3]).expanduser().resolve()

    tenant_id = legacy_tenant_id()
    result = import_orders(orders_csv, items_csv, payments_csv, tenant_id)
    print("Importação concluída:", result)
