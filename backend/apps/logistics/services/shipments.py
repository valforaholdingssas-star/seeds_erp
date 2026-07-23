from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.services import log_audit_event
from apps.geo.services import normalize_text
from apps.logistics.models import Shipment, ShipmentStatus
from apps.logistics.services.envia import generate_label
from apps.logistics.services.formatting import format_shipment
from apps.sales.services.normalization import recalculate_shipping


def ensure_shipment_for_sale(sale, *, actor=None) -> Shipment | None:
    from apps.sales.models import FulfillmentType, fulfillment_requires_envia

    ft = getattr(sale, "fulfillment_type", None) or (
        FulfillmentType.ENVIA if sale.requires_shipping else FulfillmentType.OFICINA
    )
    if not fulfillment_requires_envia(ft) or not sale.requires_shipping:
        return None
    shipment, created = Shipment.objects.get_or_create(
        sale=sale,
        defaults={
            "address_mirror": sale.address_raw,
            "city_mirror": sale.city_raw,
            "state_mirror": sale.state_raw,
            "status": ShipmentStatus.POR_GENERAR,
        },
    )
    if created:
        log_audit_event(
            actor=actor,
            action="SHIPMENT_CREATED",
            entity="Shipment",
            entity_id=str(shipment.id),
            metadata={"sale": sale.external_id},
        )
    return shipment


def contrast_destination(shipment: Shipment) -> Shipment:
    detail = {}
    warning = False
    pairs = [
        ("city", shipment.city_mirror or shipment.sale.city_raw, shipment.generated_city),
        ("state", shipment.geo_state_code or shipment.state_mirror, shipment.generated_state),
        (
            "address",
            shipment.address_formatted or shipment.address_mirror,
            shipment.generated_address,
        ),
    ]
    for field, requested, generated in pairs:
        req_n = normalize_text(requested or "")
        gen_n = normalize_text(generated or "")
        if req_n and gen_n and req_n != gen_n:
            # soft match: containment
            if req_n not in gen_n and gen_n not in req_n:
                warning = True
                detail[field] = {"pedido": requested, "generado": generated}
    shipment.warning = warning
    shipment.warning_detail = detail
    shipment.save(update_fields=["warning", "warning_detail", "updated_at"])
    return shipment


def _extract_envia_result(body: dict) -> dict:
    data = body.get("data")
    item = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else body)
    addr = item.get("address") or {}
    tracking = (
        item.get("trackingNumber")
        or item.get("tracking_number")
        or item.get("guia")
        or ""
    )
    cost = item.get("totalPrice") or item.get("Costo") or item.get("cost") or 0
    label = item.get("label") or item.get("label_url") or item.get("labelUrl") or ""
    shipment_id = str(item.get("shipmentId") or item.get("id") or "")
    return {
        "tracking_number": str(tracking),
        "shipping_cost": Decimal(str(cost or 0)),
        "label_url": str(label),
        "envia_shipment_id": shipment_id,
        "generated_city": str(addr.get("city") or item.get("city") or ""),
        "generated_state": str(addr.get("state") or item.get("state") or ""),
        "generated_address": str(addr.get("street") or item.get("street") or ""),
    }


@transaction.atomic
def generate_shipment_guide(shipment_id, *, actor=None) -> Shipment:
    from apps.sales.models import fulfillment_requires_envia

    shipment = Shipment.objects.select_for_update().select_related("sale").get(id=shipment_id)

    # Idempotency
    if shipment.tracking_number:
        return shipment

    sale = shipment.sale
    if not fulfillment_requires_envia(getattr(sale, "fulfillment_type", "ENVIA")):
        shipment.status = ShipmentStatus.GUIA_FALLIDA
        shipment.last_error = (
            f"Esta venta es {sale.fulfillment_type}: no genera guía Envia."
        )
        shipment.attempts += 1
        shipment.save()
        return shipment

    if shipment.status not in {
        ShipmentStatus.POR_GENERAR,
        ShipmentStatus.GUIA_FALLIDA,
        ShipmentStatus.REVISAR,
    }:
        raise ValueError(f"Estado no permite generar guía: {shipment.status}")

    format_shipment(shipment)
    shipment.refresh_from_db()

    if shipment.do_not_ship or not shipment.geo_city_id or not shipment.address_formatted:
        shipment.status = ShipmentStatus.GUIA_FALLIDA
        shipment.last_error = shipment.last_error or "Destino incompleto; no se llamó a Envia."
        shipment.attempts += 1
        shipment.save()
        return shipment

    try:
        body = generate_label(shipment)
        parsed = _extract_envia_result(body)
        if not parsed["tracking_number"]:
            raise RuntimeError(f"Envia no devolvió tracking: {body}")
        shipment.tracking_number = parsed["tracking_number"]
        shipment.shipping_cost = parsed["shipping_cost"]
        shipment.label_url = parsed["label_url"]
        shipment.envia_shipment_id = parsed["envia_shipment_id"]
        shipment.generated_city = parsed["generated_city"]
        shipment.generated_state = parsed["generated_state"]
        shipment.generated_address = parsed["generated_address"]
        shipment.status = ShipmentStatus.LISTO_PARA_ENVIAR
        shipment.last_error = ""
        shipment.attempts += 1
        shipment.save()
        contrast_destination(shipment)
        if shipment.shipping_cost is not None:
            recalculate_shipping(shipment.sale, shipment.shipping_cost, actor=actor)
        log_audit_event(
            actor=actor,
            action="SHIPMENT_GUIDE_OK",
            entity="Shipment",
            entity_id=str(shipment.id),
            metadata={"tracking": shipment.tracking_number},
        )
    except Exception as exc:
        shipment.status = ShipmentStatus.GUIA_FALLIDA
        shipment.last_error = str(exc)[:2000]
        shipment.attempts += 1
        shipment.save()
        log_audit_event(
            actor=actor,
            action="SHIPMENT_GUIDE_FAILED",
            entity="Shipment",
            entity_id=str(shipment.id),
            metadata={"error": str(exc)[:500]},
        )
    return shipment


@transaction.atomic
def mark_shipments_sent(ids: list, *, actor=None) -> list[Shipment]:
    updated = []
    qs = Shipment.objects.select_for_update().filter(
        id__in=ids, status=ShipmentStatus.LISTO_PARA_ENVIAR
    )
    for shipment in qs:
        # Refresh sale/items without locking outer joins
        shipment = Shipment.objects.select_related("sale").get(id=shipment.id)
        shipment.status = ShipmentStatus.ENVIADO
        shipment.sent_at = timezone.now()
        shipment.save(update_fields=["status", "sent_at", "updated_at"])
        log_audit_event(
            actor=actor,
            action="SHIPMENT_SENT",
            entity="Shipment",
            entity_id=str(shipment.id),
            metadata={"tracking": shipment.tracking_number},
        )
        # Inventory hook (filled in inventory module)
        try:
            from apps.inventory.services import discount_stock_for_shipment

            discount_stock_for_shipment(shipment, actor=actor)
        except ImportError:
            pass
        updated.append(shipment)
    return updated
