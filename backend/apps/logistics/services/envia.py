from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from django.conf import settings

from apps.config import settings_service as cfg
from apps.integrations.models import IntegrationLog, IntegrationSource
from apps.integrations.rate_limiter import TokenBucketRateLimiter, scrub_headers

logger = logging.getLogger(__name__)


def _envia_token() -> str:
    env = cfg.get("envia.environment", "sandbox") or "sandbox"
    key = "envia.token_prod" if env == "production" else "envia.token_sandbox"
    return cfg.get_secret(key) or ""


def _envia_base_url() -> str:
    # Allow override later via config; defaults from Envia docs
    env = cfg.get("envia.environment", "sandbox") or "sandbox"
    if env == "production":
        return "https://api.envia.com"
    return "https://api-test.envia.com"


def build_generate_payload(shipment) -> dict[str, Any]:
    sale = shipment.sale
    geo = shipment.geo_city
    origin = {
        "name": f"{sale.external_id} - Seeds",
        "company": "Seeds",
        "email": "seeds.atencion@gmail.com",
        "phone_code": "CO",
        "phone": "3507047110",
        "street": "Ak 7 #155C-30",
        "number": "North Point Torre E Oficina 1502",
        "city": "11001000",
        "state": "DC",
        "country": "CO",
        "identification": "901908375",
        "type": "origin",
    }
    destination = {
        "name": sale.customer_name or sale.external_id,
        "company": sale.external_id,
        "email": sale.email or "noreply@seeds.co",
        "phone": sale.phone or "3000000000",
        "country": "CO",
        "street": shipment.address_formatted or shipment.address_mirror,
        "number": "",
        "city": geo.municipality_code if geo else "",
        "state": shipment.geo_state_code,
        "identification": sale.id_number or "0",
    }
    return {
        "origin": origin,
        "destination": destination,
        "packages": [
            {
                "content": "Seeds paquetes x1",
                "amount": 1,
                "type": "box",
                "dimensions": {"length": 18, "width": 12, "height": 5},
                "weight": 0.1,
                "weightUnit": "KG",
                "lengthUnit": "CM",
                "declaredValue": 45000,
                "insurance": 45000,
            }
        ],
        "shipment": {
            "carrier": shipment.carrier or "coordinadora",
            "service": shipment.service or "ground",
            "type": 1,
        },
        "settings": {
            "printFormat": "PDF",
            "printSize": "STOCK_4X6",
            "comments": f"Guía creada automáticamente - Cliente {sale.external_id}",
        },
    }


def generate_label(shipment) -> dict[str, Any]:
    """
    Call Envia ship/generate. If no token configured, return a deterministic mock
    so local/dev flows work without credentials.
    """
    token = _envia_token()
    delay_ms = int(cfg.get_int("envia.request_delay_ms", 1200) or 1200)
    limiter = TokenBucketRateLimiter(
        "envia",
        rate_per_second=max(0.1, 1000 / max(delay_ms, 1)),
        capacity=1,
    )
    limiter.acquire(timeout=60)

    payload = build_generate_payload(shipment)
    url = f"{_envia_base_url()}/ship/generate/"
    started = time.monotonic()

    if not token:
        # Mock response for sandbox without credentials
        mock = {
            "data": [
                {
                    "trackingNumber": f"MOCK{shipment.sale.external_id[-8:].upper()}",
                    "label": "https://example.com/label.pdf",
                    "totalPrice": 12500,
                    "shipmentId": f"envia-mock-{shipment.id}",
                    "address": {
                        "city": shipment.geo_city.municipality if shipment.geo_city else "",
                        "state": shipment.geo_state_code,
                        "street": shipment.address_formatted,
                    },
                }
            ]
        }
        IntegrationLog.objects.create(
            provider=IntegrationSource.ENVIA,
            method="POST",
            url=url,
            request_headers={"Authorization": "***REDACTED***"},
            request_body=payload,
            response_status=200,
            response_body={**mock, "_mock": True},
            latency_ms=int((time.monotonic() - started) * 1000),
            success=True,
            ref_type="Shipment",
            ref_id=str(shipment.id),
        )
        return mock

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, json=payload, headers=headers)
        latency = int((time.monotonic() - started) * 1000)
        body: Any
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:2000]}
        IntegrationLog.objects.create(
            provider=IntegrationSource.ENVIA,
            method="POST",
            url=url,
            request_headers=scrub_headers(headers),
            request_body=payload,
            response_status=resp.status_code,
            response_body=body if isinstance(body, dict) else {"raw": str(body)},
            latency_ms=latency,
            success=resp.is_success,
            error="" if resp.is_success else str(body)[:1000],
            ref_type="Shipment",
            ref_id=str(shipment.id),
        )
        if not resp.is_success:
            raise RuntimeError(f"Envia {resp.status_code}: {body}")
        return body if isinstance(body, dict) else {"raw": body}
    except Exception as exc:
        IntegrationLog.objects.create(
            provider=IntegrationSource.ENVIA,
            method="POST",
            url=url,
            request_headers=scrub_headers(headers),
            request_body=payload,
            response_status=None,
            response_body={},
            latency_ms=int((time.monotonic() - started) * 1000),
            success=False,
            error=str(exc)[:1000],
            ref_type="Shipment",
            ref_id=str(shipment.id),
        )
        raise


def ping_envia() -> dict[str, Any]:
    token = _envia_token()
    if not token:
        return {
            "ok": True,
            "message": "Sin token Envia — modo mock listo (guías simuladas).",
            "mode": "mock",
        }
    url = f"{_envia_base_url()}/ship/carriers/"
    try:
        with httpx.Client(timeout=20.0) as client:
            res = client.get(url, headers={"Authorization": f"Bearer {token}"})
        if res.status_code < 300:
            return {
                "ok": True,
                "message": f"Envia OK (HTTP {res.status_code}).",
                "status": res.status_code,
                "mode": "live",
            }
        return {
            "ok": False,
            "message": f"Envia HTTP {res.status_code}: {res.text[:200]}",
            "status": res.status_code,
            "mode": "live",
        }
    except Exception as exc:
        return {"ok": False, "message": f"Error Envia: {exc}", "mode": "live"}
