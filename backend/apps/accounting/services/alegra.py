from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx

from apps.config import settings_service as cfg
from apps.integrations.models import IntegrationLog, IntegrationSource
from apps.integrations.rate_limiter import TokenBucketRateLimiter, scrub_headers

logger = logging.getLogger(__name__)

# Alegra Colombia identification types (FE catalog).
_ALEGRA_ID_TYPES = {
    "CC": "CC",
    "CEDULA": "CC",
    "CÉDULA": "CC",
    "NIT": "NIT",
    "CE": "CE",
    "TI": "TI",
    "PP": "PP",
    "PA": "PP",
    "PASAPORTE": "PP",
    "RC": "RC",
    "DE": "DIE",
    "DIE": "DIE",
    "TE": "TE",
    "NUIP": "NUIP",
    "FOREIGN_NIT": "FOREIGN_NIT",
}

# DIAN check-digit weights for NIT.
_NIT_DV_WEIGHTS = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]


def _digits_only(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def _alegra_id_type(raw: str) -> str:
    key = (raw or "CC").strip().upper()
    return _ALEGRA_ID_TYPES.get(key, "CC")


def _nit_check_digit(number: str) -> str:
    digits = [int(ch) for ch in (_digits_only(number) or "0")]
    total = sum(d * _NIT_DV_WEIGHTS[i] for i, d in enumerate(reversed(digits)))
    residue = total % 11
    return str(residue if residue in (0, 1) else 11 - residue)


def _split_person_name(full: str) -> dict[str, str]:
    parts = [p for p in (full or "").strip().split() if p]
    if not parts:
        return {"firstName": "Cliente", "lastName": "Seeds"}
    if len(parts) == 1:
        # Alegra concatena firstName+lastName; no duplicar el mismo token.
        return {"firstName": parts[0], "lastName": "-"}
    if len(parts) == 2:
        return {"firstName": parts[0], "lastName": parts[1]}
    if len(parts) == 3:
        return {
            "firstName": parts[0],
            "secondName": parts[1],
            "lastName": parts[2],
        }
    return {
        "firstName": parts[0],
        "secondName": parts[1],
        "lastName": " ".join(parts[2:]),
    }


def _is_weak_person_name(value: str, *, id_number: str = "", lead_id: str = "") -> bool:
    """True when the 'name' is really an order/lead id or empty."""
    name = (value or "").strip()
    if not name:
        return True
    if lead_id and name == str(lead_id).strip():
        return True
    if re.fullmatch(r"lead\s*#?\s*\d+", name, flags=re.IGNORECASE):
        return True
    digits = _digits_only(name)
    if digits and name.replace(" ", "").isdigit():
        return True
    if id_number and _digits_only(name) == _digits_only(id_number) and len(_digits_only(name)) >= 5:
        return True
    # Single long numeric token (Kommo often used lead id as name historically).
    if re.fullmatch(r"\d{5,}", name):
        return True
    return False


def _name_from_email(email: str) -> str:
    local = (email or "").strip().split("@", 1)[0]
    local = re.sub(r"[._+\-]+", " ", local).strip()
    if not local or local.isdigit():
        return ""
    return " ".join(p.capitalize() for p in local.split() if p)


def _name_from_related_sales(customer) -> str:
    """Prefer a real person name already stored on linked sales."""
    from apps.sales.models import ConsolidatedSale

    id_number = _digits_only(getattr(customer, "id_number", "") or "")
    qs = ConsolidatedSale.objects.filter(invoice__customer_id=customer.id)
    if id_number:
        qs = qs | ConsolidatedSale.objects.filter(id_number__icontains=id_number)
    if getattr(customer, "email", None):
        qs = qs | ConsolidatedSale.objects.filter(email__iexact=customer.email)
    for sale in qs.order_by("-created_at").only("customer_name", "id_number")[:20]:
        candidate = (sale.customer_name or "").strip()
        if not _is_weak_person_name(candidate, id_number=id_number):
            return candidate
    return ""


def _name_from_kommo_leads(customer) -> str:
    """Re-fetch Kommo contact.name for linked KOMMO sales (source of truth)."""
    from apps.sales.models import ConsolidatedSale, SaleSource
    from apps.sales.services.kommo import fetch_contact_name_for_lead

    id_number = _digits_only(getattr(customer, "id_number", "") or "")
    qs = ConsolidatedSale.objects.filter(
        source=SaleSource.KOMMO,
        invoice__customer_id=customer.id,
    )
    if id_number:
        qs = qs | ConsolidatedSale.objects.filter(
            source=SaleSource.KOMMO, id_number__icontains=id_number
        )
    if getattr(customer, "email", None):
        qs = qs | ConsolidatedSale.objects.filter(
            source=SaleSource.KOMMO, email__iexact=customer.email
        )
    seen: set[str] = set()
    for sale in qs.order_by("-created_at").only("external_id", "customer_name")[:10]:
        lead_id = str(sale.external_id or "").strip()
        if not lead_id or lead_id in seen:
            continue
        seen.add(lead_id)
        try:
            name = fetch_contact_name_for_lead(lead_id)
        except Exception as exc:
            logger.warning("Kommo name refresh failed for lead %s: %s", lead_id, exc)
            continue
        if not name or _is_weak_person_name(name, id_number=id_number, lead_id=lead_id):
            continue
        if (sale.customer_name or "").strip() != name:
            sale.customer_name = name
            sale.save(update_fields=["customer_name", "updated_at"])
        return name
    return ""


def resolve_customer_display_name(customer, *, refresh_kommo: bool = False) -> str:
    """Prefer a human name from Kommo contact / sales; never bare lead ids.

    When ``refresh_kommo`` is True (sync path), Kommo contact.name is the
    source of truth and overrides weak or email-derived placeholders.
    """
    id_number = _digits_only(getattr(customer, "id_number", "") or "")
    raw = (getattr(customer, "name", None) or "").strip()

    if refresh_kommo:
        from_kommo = _name_from_kommo_leads(customer)
        if from_kommo:
            return from_kommo

    if not _is_weak_person_name(raw, id_number=id_number):
        return raw

    from_sales = _name_from_related_sales(customer)
    if from_sales:
        return from_sales

    from_email = _name_from_email(getattr(customer, "email", "") or "")
    if from_email:
        return from_email
    if id_number:
        return f"Cliente {id_number[-4:]}"
    return "Cliente Seeds"


def _drop_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {k: _drop_empty(v) for k, v in value.items() if v is not None and v != ""}
        return {k: v for k, v in cleaned.items() if v not in (None, "", {}, [])}
    if isinstance(value, list):
        return [_drop_empty(v) for v in value if v is not None and v != ""]
    return value


def _resolve_alegra_address(customer) -> dict[str, str]:
    """Map ERP city → Alegra address {city, department, country, address}.

    Alegra CO FE rejects city without a valid DIAN department (code 2112).
    Existing Alegra contacts use e.g. city=\"Bogotá, D.C.\" + department=\"Bogotá D.C.\".
    """
    from apps.geo.models import GeoCatalog
    from apps.geo.services import is_blocked_city, resolve_city

    raw_city = (getattr(customer, "city", None) or "").strip()
    street = (getattr(customer, "address", None) or "").strip() or "Dirección no reportada"

    geo = None
    if raw_city and not is_blocked_city(raw_city):
        matches = resolve_city(raw_city, limit=1)
        geo = matches[0] if matches else None

    if geo is None:
        # Fallback: Bogotá (majority of Seeds orders / blocked tokens like DOMICILIO).
        geo = (
            GeoCatalog.objects.filter(municipality_code__startswith="11001").first()
            or GeoCatalog.objects.filter(department_iso="DC").first()
        )

    if geo is None:
        raise RuntimeError(
            f"No se pudo resolver ciudad/departamento Alegra (ciudad='{raw_city}'). "
            "Corrige la ciudad del cliente o seed del catálogo geo."
        )

    city_name = geo.municipality
    if geo.department_iso == "DC" or str(geo.municipality_code).startswith("11001"):
        city_name = "Bogotá, D.C."

    return {
        "address": street[:255],
        "city": city_name,
        "department": geo.department,
        "country": "Colombia",
    }


def build_contact_payload(customer) -> dict[str, Any]:
    """Colombia FE contact body validated against Alegra API (POST /contacts).

    Required by Alegra CO FE: identificationObject, kindOfPerson, regime.
    National IDs also need address.city + address.department + address.address.
    """
    id_type = _alegra_id_type(getattr(customer, "id_type", None) or "CC")
    raw_number = (customer.id_number or "").strip()
    id_number = _digits_only(raw_number)
    if not id_number:
        raise RuntimeError(
            "El documento del cliente no tiene dígitos numéricos "
            f"(valor: '{raw_number}'). Corrige CC/NIT antes de sincronizar con Alegra."
        )

    is_company = id_type in {"NIT", "FOREIGN_NIT"}
    kind = "LEGAL_ENTITY" if is_company else "PERSON_ENTITY"
    regime = "COMMON_REGIME" if is_company else "SIMPLIFIED_REGIME"
    full_name = resolve_customer_display_name(customer)

    identification: dict[str, Any] = {"type": id_type, "number": id_number}
    if id_type == "NIT":
        identification["dv"] = _nit_check_digit(id_number)

    payload: dict[str, Any] = {
        "kindOfPerson": kind,
        "regime": regime,
        "identificationObject": identification,
        "identification": id_number,
        "email": (customer.email or "").strip() or None,
        "phonePrimary": (customer.phone or "").strip() or None,
        "mobile": (customer.phone or "").strip() or None,
        "address": _resolve_alegra_address(customer),
        "type": ["client"],
        "status": "active",
    }
    if kind == "PERSON_ENTITY":
        payload["nameObject"] = _split_person_name(full_name)
    else:
        payload["name"] = full_name

    return _drop_empty(payload)


def _alegra_creds() -> tuple[str, str]:
    email = (cfg.get("alegra.email", "") or "").strip()
    token = (cfg.get_secret("alegra.token") or "").strip()
    return str(email), str(token)


def _alegra_base_url() -> str:
    env = cfg.get("alegra.environment", "sandbox") or "sandbox"
    if env == "production":
        return "https://api.alegra.com/api/v1"
    return "https://api.alegra.com/api/v1"  # sandbox uses same host with sandbox token


def _auth() -> tuple[str, str] | None:
    email, token = _alegra_creds()
    if not email or not token:
        return None
    return (email, token)


def _log(
    *,
    method: str,
    url: str,
    request_body: dict,
    response_status: int | None,
    response_body: dict,
    success: bool,
    error: str = "",
    latency_ms: int = 0,
    ref_type: str = "",
    ref_id: str = "",
) -> None:
    IntegrationLog.objects.create(
        provider=IntegrationSource.ALEGRA,
        method=method,
        url=url,
        request_headers={"Authorization": "***REDACTED***"},
        request_body=request_body,
        response_status=response_status,
        response_body=response_body,
        latency_ms=latency_ms,
        success=success,
        error=error,
        ref_type=ref_type,
        ref_id=ref_id,
    )


def create_or_find_contact(customer) -> dict[str, Any]:
    """POST /contacts or mock. Returns {id: alegra_id, ...}.

    If the contact already exists, PUTs name/address so weak Kommo lead-ids
    (e.g. \"13085108 13085108\") get corrected on re-sync.
    """
    auth = _auth()
    payload = build_contact_payload(customer)
    id_number = payload["identificationObject"]["number"]
    url = f"{_alegra_base_url()}/contacts"
    started = time.monotonic()

    if not auth:
        mock_id = f"mock-contact-{id_number or customer.id}"
        body = {"id": mock_id, "name": resolve_customer_display_name(customer), "_mock": True}
        _log(
            method="POST",
            url=url,
            request_body=payload,
            response_status=200,
            response_body=body,
            success=True,
            latency_ms=int((time.monotonic() - started) * 1000),
            ref_type="Customer",
            ref_id=str(customer.id),
        )
        return body

    limiter = TokenBucketRateLimiter("alegra", rate_per_second=0.8, capacity=1)
    limiter.acquire(timeout=60)
    with httpx.Client(timeout=45.0, auth=auth) as client:
        contact_id = (getattr(customer, "alegra_id", None) or "").strip()
        if not contact_id:
            search = client.get(url, params={"identification": id_number})
            if search.is_success:
                data = search.json()
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    contact_id = str(data[0].get("id") or "").strip()

        if contact_id:
            return _put_contact(
                client,
                contact_id=contact_id,
                payload=payload,
                customer=customer,
                started=started,
            )

        resp = client.post(url, json=payload)
    latency = int((time.monotonic() - started) * 1000)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:2000]}
    _log(
        method="POST",
        url=url,
        request_body=payload,
        response_status=resp.status_code,
        response_body=body if isinstance(body, dict) else {"raw": str(body)},
        success=resp.is_success,
        error="" if resp.is_success else str(body)[:1000],
        latency_ms=latency,
        ref_type="Customer",
        ref_id=str(customer.id),
    )
    if not resp.is_success:
        msg = body if isinstance(body, dict) else {"raw": str(body)}
        raise RuntimeError(f"Alegra contact {resp.status_code}: {msg}")
    return body if isinstance(body, dict) else {"id": str(body)}


def _put_contact(
    client: httpx.Client,
    *,
    contact_id: str,
    payload: dict[str, Any],
    customer,
    started: float,
) -> dict[str, Any]:
    url = f"{_alegra_base_url()}/contacts/{contact_id}"
    # Keep identity stable; refresh name / address / contact channels.
    update_body = {
        k: payload[k]
        for k in (
            "name",
            "nameObject",
            "identificationObject",
            "identification",
            "kindOfPerson",
            "regime",
            "email",
            "phonePrimary",
            "mobile",
            "address",
            "type",
            "status",
        )
        if k in payload
    }
    resp = client.put(url, json=update_body)
    latency = int((time.monotonic() - started) * 1000)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:2000]}
    if not isinstance(body, dict):
        body = {"raw": str(body)}
    body.setdefault("id", contact_id)
    _log(
        method="PUT",
        url=url,
        request_body=update_body,
        response_status=resp.status_code,
        response_body=body,
        success=resp.is_success,
        error="" if resp.is_success else str(body)[:1000],
        latency_ms=latency,
        ref_type="Customer",
        ref_id=str(customer.id),
    )
    if not resp.is_success:
        raise RuntimeError(f"Alegra contact update {resp.status_code}: {body}")
    return body


def update_contact(customer) -> dict[str, Any]:
    """PUT /contacts/{alegra_id} using the current ERP customer data."""
    auth = _auth()
    contact_id = (getattr(customer, "alegra_id", None) or "").strip()
    if not contact_id:
        raise RuntimeError("Cliente sin alegra_id para actualizar.")
    payload = build_contact_payload(customer)
    started = time.monotonic()
    if not auth:
        body = {"id": contact_id, "name": resolve_customer_display_name(customer), "_mock": True}
        _log(
            method="PUT",
            url=f"{_alegra_base_url()}/contacts/{contact_id}",
            request_body=payload,
            response_status=200,
            response_body=body,
            success=True,
            latency_ms=int((time.monotonic() - started) * 1000),
            ref_type="Customer",
            ref_id=str(customer.id),
        )
        return body
    limiter = TokenBucketRateLimiter("alegra", rate_per_second=0.8, capacity=1)
    limiter.acquire(timeout=60)
    with httpx.Client(timeout=45.0, auth=auth) as client:
        return _put_contact(
            client,
            contact_id=contact_id,
            payload=payload,
            customer=customer,
            started=started,
        )


def _alegra_get_json(client: httpx.Client, path: str, *, params: dict | None = None) -> Any:
    resp = client.get(f"{_alegra_base_url()}{path}", params=params)
    if not resp.is_success:
        raise RuntimeError(f"Alegra GET {path} {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def resolve_iva_tax_id(client: httpx.Client | None = None) -> str:
    """Return Alegra tax id for IVA 19% sales (NOT Exento/Excluido/Compras)."""
    configured = str(cfg.get("alegra.iva_tax_id", "") or "").strip()
    if configured:
        return configured
    if client is None:
        # Safe known id on Seeds account; still prefer live resolve when possible.
        return "3"
    taxes = _alegra_get_json(client, "/taxes")
    if not isinstance(taxes, list):
        return "3"
    for tax in taxes:
        name = str(tax.get("name") or "").lower()
        pct = str(tax.get("percentage") or "")
        status = str(tax.get("status") or "")
        if status and status != "active":
            continue
        if pct not in {"19", "19.00", "19.0"}:
            continue
        if "compra" in name:
            continue
        if tax.get("type") == "IVA" or "iva" in name:
            return str(tax.get("id"))
    raise RuntimeError(
        "No se encontró impuesto IVA 19% activo en Alegra. "
        "Configura alegra.iva_tax_id en Ajustes."
    )


def resolve_invoice_number_template_id(client: httpx.Client | None = None) -> str:
    configured = str(cfg.get("alegra.number_template_id", "") or "").strip()
    if configured:
        return configured
    if client is None:
        return "15"  # Seeds: Factura electrónica SDS
    templates = _alegra_get_json(client, "/number-templates")
    if not isinstance(templates, list):
        return "15"
    electronic = [
        t
        for t in templates
        if t.get("documentType") == "invoice"
        and t.get("isElectronic")
        and t.get("status") == "active"
    ]
    if not electronic:
        raise RuntimeError(
            "No hay numeración de factura electrónica activa en Alegra. "
            "Configura alegra.number_template_id."
        )
    preferred = next((t for t in electronic if t.get("isDefault")), electronic[0])
    return str(preferred.get("id"))


def resolve_invoice_item_id(client: httpx.Client | None = None) -> str:
    configured = str(cfg.get("alegra.invoice_item_id", "1") or "1").strip() or "1"
    if client is None:
        return configured
    # Validate exists; else fall back to first active service/item.
    try:
        item = _alegra_get_json(client, f"/items/{configured}")
        if isinstance(item, dict) and item.get("id"):
            return str(item.get("id"))
    except Exception:
        logger.warning("Alegra item %s no encontrado; buscando fallback", configured)
    items = _alegra_get_json(client, "/items", params={"limit": 20, "status": "active"})
    if isinstance(items, list) and items:
        return str(items[0].get("id"))
    raise RuntimeError(
        "Alegra exige id de ítem en facturas FE (code 3065). "
        "Crea un producto/servicio en Alegra y configura alegra.invoice_item_id."
    )


def build_invoice_payload(
    invoice,
    *,
    customer_alegra_id: str,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Colombia FE invoice body aligned with live Alegra account.

    Hard lessons from Seeds account:
    - tax id 1 = IVA Exento (0%). Sales IVA 19% is id 3.
    - item id is mandatory (code 3065); free-text-only items are rejected.
    - use electronic numberTemplate (SDS / id 15).
    - price must be sin IVA; Alegra adds tax.
    """
    sale = invoice.sale
    inv_date = (sale.closed_at or invoice.created_at).date().isoformat()
    net = sale.net_value if sale.net_value is not None else sale.total_value
    try:
        price = float(net or 0)
    except (TypeError, ValueError):
        price = 0.0
    if price <= 0:
        raise RuntimeError(
            f"Valor neto inválido para facturar (net_value={sale.net_value}, "
            f"total={sale.total_value})."
        )

    tax_id = resolve_iva_tax_id(client)
    template_id = resolve_invoice_number_template_id(client)
    item_id = resolve_invoice_item_id(client)

    payload: dict[str, Any] = {
        "date": inv_date,
        "dueDate": inv_date,
        "client": {"id": str(customer_alegra_id)},
        "numberTemplate": {"id": str(template_id)},
        "paymentForm": "CASH",
        "paymentMethod": "INSTRUMENT_NOT_DEFINED",
        "items": [
            {
                "id": int(item_id) if str(item_id).isdigit() else item_id,
                "price": price,
                "quantity": 1,
                "tax": [{"id": int(tax_id) if str(tax_id).isdigit() else tax_id}],
                "description": f"Seeds · pedido {sale.external_id}",
            }
        ],
        "anotation": f"Seeds ERP {invoice.idempotency_key}",
        "status": "open",
    }
    return payload


def create_invoice(invoice, *, customer_alegra_id: str) -> dict[str, Any]:
    auth = _auth()
    sale = invoice.sale
    url = f"{_alegra_base_url()}/invoices"
    started = time.monotonic()
    payload = build_invoice_payload(invoice, customer_alegra_id=customer_alegra_id)

    if not auth:
        body = {
            "id": f"mock-inv-{invoice.idempotency_key}",
            "number": f"FE-{str(sale.external_id)[-6:]}",
            "cufe": f"CUFE-MOCK-{sale.external_id}",
            "pdf": "https://example.com/invoice.pdf",
            "_mock": True,
        }
        _log(
            method="POST",
            url=url,
            request_body=payload,
            response_status=200,
            response_body=body,
            success=True,
            latency_ms=int((time.monotonic() - started) * 1000),
            ref_type="Invoice",
            ref_id=str(invoice.id),
        )
        return body

    limiter = TokenBucketRateLimiter("alegra", rate_per_second=0.8, capacity=1)
    limiter.acquire(timeout=60)
    headers = {"Idempotency-Key": invoice.idempotency_key}
    with httpx.Client(timeout=45.0, auth=auth) as client:
        payload = build_invoice_payload(
            invoice, customer_alegra_id=customer_alegra_id, client=client
        )
        resp = client.post(url, json=payload, headers=headers)
    latency = int((time.monotonic() - started) * 1000)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:2000]}
    _log(
        method="POST",
        url=url,
        request_body=payload,
        response_status=resp.status_code,
        response_body=body if isinstance(body, dict) else {"raw": str(body)},
        success=resp.is_success,
        error="" if resp.is_success else str(body)[:1000],
        latency_ms=latency,
        ref_type="Invoice",
        ref_id=str(invoice.id),
    )
    if not resp.is_success:
        raise RuntimeError(f"Alegra invoice {resp.status_code}: {body}")
    return body if isinstance(body, dict) else {"id": str(body)}


def find_invoice_by_annotation(idempotency_key: str) -> dict[str, Any] | None:
    """Reconcile: search Alegra for invoice created despite timeout."""
    auth = _auth()
    if not auth:
        # In mock mode, nothing to reconcile remotely
        return None
    url = f"{_alegra_base_url()}/invoices"
    with httpx.Client(timeout=45.0, auth=auth) as client:
        resp = client.get(url, params={"query": idempotency_key})
    if not resp.is_success:
        return None
    data = resp.json()
    if isinstance(data, list):
        for item in data:
            note = str(item.get("anotation") or item.get("annotation") or "")
            if idempotency_key in note:
                return item
        return data[0] if data else None
    return data if isinstance(data, dict) else None


def create_credit_note(invoice, *, reason: str) -> dict[str, Any]:
    auth = _auth()
    payload = {
        "invoice": {"id": invoice.alegra_id},
        "date": invoice.confirmed_at.date().isoformat()
        if invoice.confirmed_at
        else invoice.updated_at.date().isoformat(),
        "observations": reason[:500],
    }
    url = f"{_alegra_base_url()}/credit-notes"
    started = time.monotonic()
    if not auth:
        body = {"id": f"mock-cn-{invoice.id}", "_mock": True}
        _log(
            method="POST",
            url=url,
            request_body=payload,
            response_status=200,
            response_body=body,
            success=True,
            latency_ms=int((time.monotonic() - started) * 1000),
            ref_type="Invoice",
            ref_id=str(invoice.id),
        )
        return body

    limiter = TokenBucketRateLimiter("alegra", rate_per_second=0.8, capacity=1)
    limiter.acquire(timeout=60)
    with httpx.Client(timeout=45.0, auth=auth) as client:
        resp = client.post(url, json=payload)
    latency = int((time.monotonic() - started) * 1000)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:2000]}
    _log(
        method="POST",
        url=url,
        request_body=payload,
        response_status=resp.status_code,
        response_body=body if isinstance(body, dict) else {"raw": str(body)},
        success=resp.is_success,
        error="" if resp.is_success else str(body)[:1000],
        latency_ms=latency,
        ref_type="Invoice",
        ref_id=str(invoice.id),
    )
    if not resp.is_success:
        raise RuntimeError(f"Alegra credit-note {resp.status_code}: {body}")
    return body if isinstance(body, dict) else {"id": str(body)}


def ping_alegra() -> dict[str, Any]:
    auth = _auth()
    if not auth:
        return {
            "ok": True,
            "message": "Sin credenciales Alegra — modo mock listo (facturas simuladas).",
            "mode": "mock",
        }
    url = f"{_alegra_base_url()}/company"
    try:
        with httpx.Client(timeout=20.0, auth=auth) as client:
            res = client.get(url)
        if res.status_code < 300:
            return {
                "ok": True,
                "message": f"Alegra OK (HTTP {res.status_code}).",
                "status": res.status_code,
                "mode": "live",
            }
        # fallback contacts
        with httpx.Client(timeout=20.0, auth=auth) as client:
            res = client.get(f"{_alegra_base_url()}/contacts", params={"limit": 1})
        if res.status_code < 300:
            return {
                "ok": True,
                "message": f"Alegra OK via contacts (HTTP {res.status_code}).",
                "status": res.status_code,
                "mode": "live",
            }
        return {
            "ok": False,
            "message": (
                f"Alegra HTTP {res.status_code}: {res.text[:200]}. "
                "Revisa email + token API (Configuración → Alegra en Alegra.com → "
                "API / Integraciones). Guarda antes de probar. No uses la contraseña "
                "de login: debe ser el token de API."
            ),
            "status": res.status_code,
            "mode": "error",
        }
    except Exception as exc:
        return {"ok": False, "message": f"Error Alegra: {exc}", "mode": "live"}
