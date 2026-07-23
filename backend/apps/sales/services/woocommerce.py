from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.sales.models import EcommerceSale, SaleSource
from apps.sales.services.normalization import (
    apply_status_transition,
    extract_woo_id_number,
    parse_woo_line_items,
    promote_to_consolidated,
)
from apps.sales.services.payment_methods import resolve_payment_method


def _parse_closed_at(value) -> timezone.datetime | None:
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value
    dt = parse_datetime(str(value))
    if dt and timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


@transaction.atomic
def upsert_ecommerce_from_payload(payload: dict, *, raw_event=None, actor=None):
    body = payload.get("body") if isinstance(payload.get("body"), dict) else payload
    order_id = str(body.get("id") or "")
    if not order_id:
        raise ValueError("WooCommerce payload sin id de orden")

    billing = body.get("billing") or {}
    address_1 = billing.get("address_1") or ""
    address_2 = billing.get("address_2") or ""
    address = " - ".join([p for p in [address_1, address_2] if p])

    items, qty_d, qty_p = parse_woo_line_items(body.get("line_items"))
    status = str(body.get("status") or "pending")

    # Plugin Seeds envía id_number canónico; fallback a meta_data por key
    id_number = str(body.get("id_number") or "").strip()
    if not id_number:
        id_number = extract_woo_id_number(body.get("meta_data"))

    payment_raw = str(
        body.get("payment_method_title") or body.get("payment_method") or "Mercadopago"
    )
    payment_method = resolve_payment_method(payment_raw, actor=actor)

    sale, _ = EcommerceSale.objects.update_or_create(
        external_id=order_id,
        defaults={
            "raw_event": raw_event,
            "deal_name": f"Orden {order_id}",
            "closed_at": _parse_closed_at(body.get("date_created")),
            "total_value": Decimal(str(body.get("total") or "0")),
            "amount_shipping": Decimal(str(body.get("shipping_total") or "0")),
            "payment_account": payment_method.name if payment_method else payment_raw,
            "payment_method": payment_method,
            "income_source": "E-COMMERCE",
            "status": status,
            "stage": "Cierre ganado",
            "commercial_raw": "ECOMMERCE",
            "customer_name": f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
            "email": billing.get("email") or "",
            "phone": billing.get("phone") or "",
            "id_number": id_number,
            "address_raw": address,
            "city_raw": billing.get("city") or "",
            "state_raw": billing.get("state") or "",
            "qty_dorados": qty_d,
            "qty_plateados": qty_p,
            "order_notes": str(body.get("customer_note") or ""),
            "extra": {
                "customer_id": body.get("customer_id"),
                "payment_method": body.get("payment_method"),
            },
        },
    )
    return apply_status_transition(
        sale,
        source=SaleSource.ECOMMERCE,
        new_status=status,
        items=items,
        actor=actor,
    ) or sale
