from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from apps.config import settings_service as cfg
from apps.integrations.models import IntegrationLog, IntegrationSource
from apps.integrations.rate_limiter import TokenBucketRateLimiter, scrub_headers

logger = logging.getLogger(__name__)


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
    """POST /contacts or mock. Returns {id: alegra_id, ...}."""
    auth = _auth()
    id_type = (getattr(customer, "id_type", None) or "CC").strip().upper() or "CC"
    id_number = (customer.id_number or "").strip()
    payload: dict[str, Any] = {
        "name": (customer.name or id_number or "Cliente").strip(),
        "identification": id_number or None,
        "identificationObject": {
            "type": id_type,
            "number": id_number,
        },
        "email": (customer.email or "").strip() or None,
        "phonePrimary": (customer.phone or "").strip() or None,
        "address": {
            "address": (customer.address or "").strip() or None,
            "city": (customer.city or "").strip() or None,
        },
        "type": ["client"],
        "status": "active",
    }
    # Drop empty nested values Alegra rejects
    if not payload["address"]["address"] and not payload["address"]["city"]:
        payload.pop("address", None)
    else:
        payload["address"] = {
            k: v for k, v in payload["address"].items() if v
        }
    url = f"{_alegra_base_url()}/contacts"
    started = time.monotonic()

    if not auth:
        mock_id = f"mock-contact-{customer.id_number or customer.id}"
        body = {"id": mock_id, "name": customer.name, "_mock": True}
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
        # search first
        if id_number:
            search = client.get(url, params={"identification": id_number})
            if search.is_success:
                data = search.json()
                if isinstance(data, list) and data:
                    found = data[0] if isinstance(data[0], dict) else {"id": data[0]}
                    _log(
                        method="GET",
                        url=url,
                        request_body={"identification": id_number},
                        response_status=search.status_code,
                        response_body=found if isinstance(found, dict) else {"raw": str(found)},
                        success=True,
                        latency_ms=int((time.monotonic() - started) * 1000),
                        ref_type="Customer",
                        ref_id=str(customer.id),
                    )
                    return found
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
        raise RuntimeError(f"Alegra contact {resp.status_code}: {body}")
    return body if isinstance(body, dict) else {"id": str(body)}


def create_invoice(invoice, *, customer_alegra_id: str) -> dict[str, Any]:
    auth = _auth()
    sale = invoice.sale
    payload = {
        "date": (sale.closed_at or invoice.created_at).date().isoformat(),
        "dueDate": (sale.closed_at or invoice.created_at).date().isoformat(),
        "client": {"id": customer_alegra_id},
        "items": [
            {
                "name": f"Seeds · pedido {sale.external_id}",
                "price": float(sale.net_value or sale.total_value),
                "quantity": 1,
                "tax": [{"id": 1, "name": "IVA", "percentage": 19}],
            }
        ],
        "anotation": f"Seeds ERP {invoice.idempotency_key}",
        "status": "open",
    }
    url = f"{_alegra_base_url()}/invoices"
    started = time.monotonic()

    if not auth:
        body = {
            "id": f"mock-inv-{invoice.idempotency_key}",
            "number": f"FE-{sale.external_id[-6:]}",
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
