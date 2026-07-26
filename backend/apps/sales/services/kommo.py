from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal, InvalidOperation
import re

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

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


def _cf_any(values: list[dict] | None, *field_names: str) -> str:
    for name in field_names:
        found = _cf(values, field_name=name)
        if found:
            return found
    return ""


def _parse_money(value) -> Decimal:
    """Parse Kommo/CO money: '9.500' → 9500, '9500' → 9500, '9,5' → 9.5."""
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    raw = str(value).strip().replace("$", "").replace(" ", "")
    if not raw:
        return Decimal("0")
    # 1.234.567,89 or 9.500,00
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", raw):
        raw = raw.replace(".", "").replace(",", ".")
    # 1234,56
    elif "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    # 9.500 (thousands) vs 9.5 (decimal)
    elif re.fullmatch(r"\d+\.\d{3}", raw):
        raw = raw.replace(".", "")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def _parse_kommo_closed_at(value) -> datetime | None:
    """Parse Kommo FECHA DE CIERRE (epoch s/ms, ISO, or YYYY-MM-DD). Never invents 'now'."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value
    raw = str(value).strip()
    if not raw:
        return None
    tz = timezone.get_current_timezone()
    # Numeric epoch (seconds or milliseconds)
    try:
        num = float(raw.replace(",", "."))
        if num > 1e12:  # ms
            num /= 1000.0
        if num > 1e9:  # plausible unix timestamp
            return datetime.fromtimestamp(num, tz=tz)
    except (TypeError, ValueError, OSError, OverflowError):
        pass
    dt = parse_datetime(raw)
    if dt:
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, tz)
        return dt
    d = parse_date(raw[:10]) if len(raw) >= 10 else parse_date(raw)
    if d:
        return timezone.make_aware(datetime.combine(d, time.min), tz)
    return None


def _is_weak_kommo_name(value: str, *, lead_id: str = "") -> bool:
    v = (value or "").strip()
    if not v:
        return True
    if lead_id and v == str(lead_id).strip():
        return True
    if v.isdigit():
        return True
    if re.fullmatch(r"lead\s*#?\s*\d+", v, flags=re.IGNORECASE):
        return True
    return False


def fetch_contact_name_for_lead(lead_id: str) -> str:
    """Live Kommo contact.name for a lead (person name, not lead title)."""
    from apps.sales.services.kommo_client import fetch_contact, fetch_lead, kommo_configured

    lead_id = str(lead_id or "").strip()
    if not lead_id or not kommo_configured():
        return ""
    lead = fetch_lead(lead_id)
    embedded = (lead.get("_embedded") or {}).get("contacts") or []
    if not embedded:
        return ""
    cid = str(embedded[0].get("id") or "").strip()
    if not cid:
        return ""
    contact = fetch_contact(cid)
    name = (contact.get("name") or "").strip()
    if name and not _is_weak_kommo_name(name, lead_id=lead_id):
        return name
    first = (contact.get("first_name") or "").strip()
    last = (contact.get("last_name") or "").strip()
    combined = f"{first} {last}".strip()
    if combined and not _is_weak_kommo_name(combined, lead_id=lead_id):
        return combined
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

    closed_raw = _cf_any(
        cfs,
        "FECHA DE CIERRE",
        "Fecha de cierre",
        "Fecha de Cierre",
        "fecha de cierre",
    )
    closed_at = _parse_kommo_closed_at(closed_raw)

    total = _parse_money(lead.get("price") or 0)
    shipping = _parse_money(
        _cf_any(
            cfs,
            "Recaudado envio",
            "Recaudado envío",
            "Recaudado Envio",
            "TRASPORTE",
            "Transporte",
        )
    )
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

    # Source of truth: Kommo CONTACT name (not lead title "Lead #id").
    contact_name = (contact.get("name") or "").strip()
    if not contact_name:
        first = (contact.get("first_name") or "").strip()
        last = (contact.get("last_name") or "").strip()
        contact_name = f"{first} {last}".strip()
    lead_name = (lead.get("name") or "").strip()

    customer_name = ""
    if contact_name and not _is_weak_kommo_name(contact_name, lead_id=lead_id):
        customer_name = contact_name
    elif lead_name and not _is_weak_kommo_name(lead_name, lead_id=lead_id):
        customer_name = lead_name
    elif email:
        local = email.split("@", 1)[0]
        local = local.replace(".", " ").replace("_", " ").replace("+", " ").strip()
        if local and not local.isdigit():
            customer_name = " ".join(p.capitalize() for p in local.split())
    if not customer_name:
        customer_name = contact_name or lead_name or lead_id

    sale, _ = KommoSale.objects.update_or_create(
        external_id=lead_id,
        defaults={
            "raw_event": raw_event,
            "deal_name": lead.get("name") or "",
            "closed_at": closed_at,
            "total_value": total,
            "amount_shipping": shipping,
            "payment_account": payment_method.name if payment_method else payment_raw,
            "payment_method": payment_method,
            "income_source": "KOMMO",
            "status": "processing",
            "stage": "Cierre ganado",
            "commercial_raw": _cf(cfs, field_name="Comercial"),
            "customer_name": customer_name,
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
