from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.sales.models import SaleSource, ShopifySale
from apps.sales.services.normalization import (
    apply_status_transition,
    extract_shopify_id_number,
    parse_shopify_line_items,
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


def map_shopify_status(body: dict) -> str:
    """
    Map Shopify → ERP intake statuses (same gate as Woo).

    Solo entran al consolidado: processing / completed
      ↔ Shopify financial_status == paid
        (fulfilled → completed; paid sin fulfill → processing)

    No consolidan: pending, authorized, partially_paid
    Retiran: cancelled / refunded / voided
    """
    if body.get("cancelled_at") or body.get("cancel_reason"):
        return "cancelled"

    financial = str(body.get("financial_status") or "").lower()
    if financial in {"refunded", "voided"}:
        return "refunded"
    if financial == "paid":
        fulfillment = str(body.get("fulfillment_status") or "").lower()
        if fulfillment == "fulfilled":
            return "completed"
        return "processing"
    # pending | authorized | partially_paid | partially_refunded | …
    # partially_refunded: si ya estaba consolidado, apply_status_transition
    # lo mantiene/retira según WITHDRAW; no promovemos de nuevo desde aquí
    # salvo que siga "paid" (arriba).
    if financial == "partially_refunded":
        # Pedido ya cobrado parcialmente reembolsado: sigue siendo venta activa.
        return "processing"
    return "pending"


def _shipping_total(body: dict) -> Decimal:
    lines = body.get("shipping_lines") or []
    total = Decimal("0")
    for line in lines:
        total += Decimal(str(line.get("price") or "0"))
    if total:
        return total
    # Fallback: total - subtotal when shipping_lines empty
    try:
        total_price = Decimal(str(body.get("total_price") or "0"))
        subtotal = Decimal(str(body.get("subtotal_price") or "0"))
        if total_price > subtotal:
            return (total_price - subtotal).quantize(Decimal("0.01"))
    except Exception:
        pass
    return Decimal("0")


def _address_block(body: dict) -> dict:
    shipping = body.get("shipping_address") or {}
    billing = body.get("billing_address") or {}
    return shipping if shipping else billing


@transaction.atomic
def upsert_shopify_from_payload(payload: dict, *, raw_event=None, actor=None):
    body = payload.get("body") if isinstance(payload.get("body"), dict) else payload
    # Webhook sometimes wraps as {"order": {...}} when pulled via Admin API
    if isinstance(body.get("order"), dict) and not body.get("id"):
        body = body["order"]

    order_id = str(body.get("id") or "")
    if not order_id:
        raise ValueError("Shopify payload sin id de orden")

    addr = _address_block(body)
    address_1 = addr.get("address1") or ""
    address_2 = addr.get("address2") or ""
    address = " - ".join([p for p in [address_1, address_2] if p])

    items, qty_d, qty_p = parse_shopify_line_items(body.get("line_items"))
    status = map_shopify_status(body)

    first = addr.get("first_name") or ""
    last = addr.get("last_name") or ""
    customer_name = f"{first} {last}".strip()
    if not customer_name:
        customer = body.get("customer") or {}
        customer_name = (
            f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            or str(body.get("email") or body.get("name") or f"Orden {order_id}")
        )

    id_number = extract_shopify_id_number(
        body.get("note_attributes"),
        note=str(body.get("note") or ""),
        metafields=body.get("metafields") if isinstance(body.get("metafields"), list) else None,
    )

    gateway = ""
    gateways = body.get("payment_gateway_names") or []
    if isinstance(gateways, list) and gateways:
        gateway = str(gateways[0])
    payment_raw = gateway or str(body.get("gateway") or "Shopify")
    payment_method = resolve_payment_method(payment_raw, actor=actor)

    phone = (
        str(addr.get("phone") or "").strip()
        or str(body.get("phone") or "").strip()
        or str((body.get("customer") or {}).get("phone") or "").strip()
    )

    sale, _ = ShopifySale.objects.update_or_create(
        external_id=order_id,
        defaults={
            "raw_event": raw_event,
            "deal_name": str(body.get("name") or f"Orden {order_id}"),
            "closed_at": _parse_closed_at(body.get("created_at") or body.get("processed_at")),
            "total_value": Decimal(str(body.get("total_price") or body.get("current_total_price") or "0")),
            "amount_shipping": _shipping_total(body),
            "payment_account": payment_method.name if payment_method else payment_raw,
            "payment_method": payment_method,
            "income_source": "SHOPIFY",
            "status": status,
            "stage": "Cierre ganado",
            "commercial_raw": "SHOPIFY",
            "customer_name": customer_name,
            "email": str(body.get("email") or (body.get("customer") or {}).get("email") or ""),
            "phone": phone,
            "id_number": id_number,
            "address_raw": address,
            "city_raw": str(addr.get("city") or ""),
            "state_raw": str(addr.get("province") or addr.get("province_code") or ""),
            "qty_dorados": qty_d,
            "qty_plateados": qty_p,
            "order_notes": str(body.get("note") or ""),
            "extra": {
                "order_number": body.get("order_number") or body.get("name"),
                "financial_status": body.get("financial_status"),
                "fulfillment_status": body.get("fulfillment_status"),
                "shopify_shop": (raw_event.headers or {}).get("X-Shopify-Shop-Domain")
                if raw_event
                else None,
                "tags": body.get("tags"),
            },
        },
    )
    return apply_status_transition(
        sale,
        source=SaleSource.SHOPIFY,
        new_status=status,
        items=items,
        actor=actor,
    ) or sale
