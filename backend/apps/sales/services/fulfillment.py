from __future__ import annotations

from apps.sales.models import FulfillmentType, fulfillment_requires_envia


def normalize_fulfillment_type(raw: str | None, *, requires_shipping: bool | None = None) -> str:
    """
    Acepta códigos o texto libre (CSV/Kommo/UI) → FulfillmentType.
    Si no hay señal clara, usa requires_shipping (True→ENVIA, False→OFICINA).
    """
    text = (raw or "").strip().lower()
    aliases = {
        "envia": FulfillmentType.ENVIA,
        "envía": FulfillmentType.ENVIA,
        "guia": FulfillmentType.ENVIA,
        "guía": FulfillmentType.ENVIA,
        "courier": FulfillmentType.ENVIA,
        "envio": FulfillmentType.ENVIA,
        "envío": FulfillmentType.ENVIA,
        "domicilio": FulfillmentType.DOMICILIO,
        "domicilio externo": FulfillmentType.DOMICILIO,
        "domicilio fuera de envia": FulfillmentType.DOMICILIO,
        "entrega local": FulfillmentType.DOMICILIO,
        "mensajero": FulfillmentType.DOMICILIO,
        "oficina": FulfillmentType.OFICINA,
        "visita": FulfillmentType.OFICINA,
        "recoger": FulfillmentType.OFICINA,
        "pickup": FulfillmentType.OFICINA,
        "pasar a la oficina": FulfillmentType.OFICINA,
    }
    if text in {c.value.lower() for c in FulfillmentType}:
        return text.upper()
    if text in aliases:
        return aliases[text]
    for key, value in aliases.items():
        if key in text:
            return value
    if requires_shipping is False:
        return FulfillmentType.OFICINA
    return FulfillmentType.ENVIA


def apply_fulfillment(data: dict) -> dict:
    """Normaliza fulfillment_type + requires_shipping en un dict de venta."""
    ft = normalize_fulfillment_type(
        data.get("fulfillment_type"),
        requires_shipping=data.get("requires_shipping"),
    )
    data["fulfillment_type"] = ft
    data["requires_shipping"] = fulfillment_requires_envia(ft)
    return data


def sync_shipment_for_fulfillment(sale, *, actor=None) -> None:
    """
    ENVIA → asegura Shipment.
    DOMICILIO/OFICINA → elimina envíos pendientes (no tocamos ENVIADO).
    """
    from apps.logistics.models import Shipment, ShipmentStatus
    from apps.logistics.services.shipments import ensure_shipment_for_sale
    from apps.audit.services import log_audit_event

    if fulfillment_requires_envia(sale.fulfillment_type):
        ensure_shipment_for_sale(sale, actor=actor)
        return

    removable = Shipment.objects.filter(sale=sale).exclude(
        status__in=[ShipmentStatus.ENVIADO]
    )
    for shipment in removable:
        sid = str(shipment.id)
        shipment.delete()
        log_audit_event(
            actor=actor,
            action="SHIPMENT_REMOVED_NO_ENVIA",
            entity="Shipment",
            entity_id=sid,
            metadata={
                "sale": sale.external_id,
                "fulfillment_type": sale.fulfillment_type,
            },
        )
