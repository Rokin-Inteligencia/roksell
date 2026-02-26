from __future__ import annotations

from datetime import datetime
import re


def _fmt_money(value_cents: int) -> str:
    value = (value_cents or 0) / 100
    s = f"{value:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso


def format_money(value_cents: int) -> str:
    return _fmt_money(value_cents)


def format_status_items(items: list[dict]) -> str:
    return (
        "\n".join(
            [
                f"- {item['name']} {item['quantity']} x R$ {_fmt_money(item['unit_price_cents'])}"
                for item in items
            ]
        )
        if items
        else "- (sem itens)"
    )


_TEMPLATE_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def render_template(template: str, values: dict[str, str]) -> str:
    if not template:
        return ""

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        return str(values.get(key, match.group(0)))

    return _TEMPLATE_PATTERN.sub(_replace, template)


def format_order_message(
    *,
    order_id: str,
    customer_name: str,
    phone: str,
    pickup: bool,
    address_text: str,
    window_start: str | None,
    window_end: str | None,
    delivery_date: str | None,
    items: list[dict],
    payment_method: str,
    subtotal_cents: int,
    shipping_cents: int,
    discount_cents: int,
    total_cents: int,
) -> str:
    items_text = (
        "\n".join(
            [
                f"- {item['name']} x{item['quantity']} -> R$ {_fmt_money(item['unit_price_cents'])}"
                for item in items
            ]
        )
        if items
        else "- (no items)"
    )
    delivery_mode = "*Pickup:* Yes" if pickup else "*Delivery:* Yes"
    return (
        f"*New order*\n"
        f"*ID:* `{order_id}`\n"
        f"*Customer:* {customer_name}\n"
        f"*Phone:* `{phone}`\n"
        f"{delivery_mode}\n\n"
        f"*Delivery date:* {delivery_date or '-'}\n"
        f"*Window:* {_fmt_dt(window_start)} -> {_fmt_dt(window_end)}\n"
        f"*Address:*\n{address_text}\n\n"
        f"*Items:*\n{items_text}\n\n"
        f"*Payment:* {payment_method}\n"
        f"*Subtotal:* R$ {_fmt_money(subtotal_cents)}\n"
        f"*Shipping:* R$ {_fmt_money(shipping_cents)}\n"
        f"*Discount:* R$ {_fmt_money(discount_cents)}\n"
        f"*Total:* *R$ {_fmt_money(total_cents)}*"
    )


def format_order_status_message(
    *,
    order_code: str,
    customer_name: str,
    status_text: str,
    items: list[dict],
    shipping_cents: int,
    discount_cents: int,
    total_cents: int,
    delivery_type: str,
    address_text: str,
) -> str:
    items_text = format_status_items(items)
    lines = [
        f"Ol\u00e1, {customer_name}.",
        "",
        f"Seu pedido {order_code} foi atualizado para: {status_text}",
        "Itens:",
        items_text,
        "",
    ]
    if shipping_cents > 0:
        lines.append(f"Frete: R$ {_fmt_money(shipping_cents)}")
    if discount_cents > 0:
        lines.append(f"Desconto: R$ {_fmt_money(discount_cents)}")
    lines.append(f"*Valor total: R$ {_fmt_money(total_cents)}*")
    lines.append("")
    lines.append(f"Tipo de entrega: {delivery_type}")
    lines.append("Endere\u00e7o:")
    lines.append(address_text or "-")
    lines.append("")
    lines.append(f"Qualquer d\u00favida, estamos \u00e0 disposi\u00e7\u00e3o! \U0001f36a\U0001f90e")
    return "\n".join(lines)
