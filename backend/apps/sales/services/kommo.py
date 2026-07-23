from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.sales.models import KommoSale, SaleSource
from apps.sales.services.normalization import promote_to_consolidated
from apps.sales.services.payment_methods import resolve_payment_method


def _cf(values: list[dict] | None, *, field_name: str | None = None, field_code: str | None = None) -> str:
    for item in values or []:
        if field_name and item.get("field_name") == field_name:
            vals = item.get("values") or []
            if vals:
                return str(vals[0].get("value") or "")
        if field_code and item.get("field_code") == field_code:
            vals = item.get("values") or []
            if vals:
                return str(vals[0].get("value") or "")
    return ""


@transaction.atomic
def upsert_kommo_from_enriched(
    *,
    lead: dict,
    contact: dict | None = None,
    raw_event=None,
    actor=None,
):
    """
    Expects already-fetched lead (+ optional contact) from Kommo API.
    Webhook alone only brings ids; enrichment happens in the task/client.
    """
    lead_id = str(lead.get("id") or "")
    if not lead_id:
        raise ValueError("Kommo lead sin id")

    cfs = lead.get("custom_fields_values") or []
    contact = contact or {}
    contact_cfs = contact.get("custom_fields_values") or []

    closed_raw = _cf(cfs, field_name="FECHA DE CIERRE")
    closed_at = None
    if closed_raw:
        try:
            # Kommo often sends epoch seconds
            ts = int(float(closed_raw))
            closed_at = timezone.datetime.fromtimestamp(ts, tz=timezone.get_current_timezone())
        except Exception:
            closed_at = timezone.now()

    total = Decimal(str(lead.get("price") or 0))
    # Kommo: neto = valor/1.19, transporte = 0 inicial
    qty_d = int(float(_cf(cfs, field_name="# Seeds Dorados") or 0) or 0)
    qty_p = int(float(_cf(cfs, field_name="# Seeds plateados") or 0) or 0)

    email = _cf(contact_cfs, field_code="EMAIL")
    phone = _cf(contact_cfs, field_code="PHONE")
    # n8n: cédula del contacto; fallback al custom field CC del lead
    id_number = (
        _cf(contact_cfs, field_name="Cédula de ciudadanía")
        or _cf(cfs, field_name="CC")
        or _cf(cfs, field_name="Cédula de ciudadanía")
    )
    payment_raw = _cf(cfs, field_name="Medio de pago")
    payment_method = resolve_payment_method(payment_raw, actor=actor)

    sale, _ = KommoSale.objects.update_or_create(
        external_id=lead_id,
        defaults={
            "raw_event": raw_event,
            "deal_name": lead.get("name") or "",
            "closed_at": closed_at or timezone.now(),
            "total_value": total,
            "amount_shipping": Decimal("0"),
            "payment_account": payment_method.name if payment_method else payment_raw,
            "payment_method": payment_method,
            "income_source": "KOMMO",
            "status": "processing",
            "stage": "Cierre ganado",
            "commercial_raw": _cf(cfs, field_name="Comercial"),
            "customer_name": contact.get("name") or lead.get("name") or "",
            "email": email,
            "phone": phone,
            "id_number": id_number,
            "address_raw": _cf(cfs, field_name="Dirección entrega")
            or _cf(cfs, field_name="Direccion entrega"),
            "city_raw": _cf(cfs, field_name="Ciudad"),
            "qty_dorados": qty_d,
            "qty_plateados": qty_p,
            "tipo_dorados": _cf(cfs, field_name="Tipo dorados"),
            "tipo_plateados": _cf(cfs, field_name="Tipo plateados"),
            "symptoms": _cf(cfs, field_name="Síntoma/s"),
            "order_notes": _cf(cfs, field_name="NOTAS DEL PEDIDO"),
            "age": _cf(cfs, field_name="Edad"),
            "extra": {
                "pipeline_id": lead.get("pipeline_id"),
                "status_id": lead.get("status_id"),
                "fuente_ingreso": _cf(cfs, field_name="Fuente de ingreso"),
                "fuente": _cf(cfs, field_name="FUENTE"),
                "formateador_id": f"SEEDS-{lead_id}",
            },
        },
    )
    return promote_to_consolidated(sale, source=SaleSource.KOMMO, actor=actor)
