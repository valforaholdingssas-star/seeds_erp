from __future__ import annotations

import re
import unicodedata

from apps.geo.services import is_blocked_city, normalize_text, resolve_city
from apps.logistics.models import Shipment, ShipmentStatus

ADDRESS_REPLACEMENTS = (
    (r"\bcalle\b", "cll"),
    (r"\bcl\b", "cll"),
    (r"\bcarrera\b", "cra"),
    (r"\bkr\b", "cra"),
    (r"\bcr\b", "cra"),
    (r"\btransversal\b", "tv"),
    (r"\bdiagonal\b", "dg"),
    (r"\bavenida\b", "av"),
    (r"\bno\b", "#"),
    (r"\bnumero\b", "#"),
    (r"\bnúmero\b", "#"),
)


def format_address_local(raw: str) -> str:
    value = (raw or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    for pattern, repl in ADDRESS_REPLACEMENTS:
        value = re.sub(pattern, repl, value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def format_shipment(shipment: Shipment) -> Shipment:
    """Catalog-first city resolve + local address formatting. LLM fallback later."""
    city_raw = shipment.city_mirror or shipment.sale.city_raw
    address_raw = shipment.address_mirror or shipment.sale.address_raw

    if is_blocked_city(city_raw) or not normalize_text(address_raw):
        shipment.do_not_ship = True
        shipment.status = ShipmentStatus.REVISAR
        shipment.last_error = "Ciudad/dirección no enviable (vacía, Domicilio, Recoger…)."
        shipment.geo_city = None
        shipment.geo_state_code = ""
        shipment.address_formatted = ""
        shipment.save()
        return shipment

    matches = resolve_city(city_raw, limit=1)
    if not matches:
        shipment.do_not_ship = True
        shipment.status = ShipmentStatus.REVISAR
        shipment.last_error = "Ciudad no resuelta en catálogo DANE."
        shipment.save()
        return shipment

    geo = matches[0]
    shipment.geo_city = geo
    shipment.geo_state_code = geo.department_iso
    shipment.address_formatted = format_address_local(address_raw)
    shipment.do_not_ship = False
    if shipment.status == ShipmentStatus.REVISAR:
        shipment.status = ShipmentStatus.POR_GENERAR
        shipment.last_error = ""
    shipment.save()
    return shipment
