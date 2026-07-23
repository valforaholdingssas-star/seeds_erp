from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.config import settings_service as cfg
from apps.integrations.models import IntegrationLog, IntegrationSource

logger = logging.getLogger(__name__)


def _kommo_base() -> str:
    sub = (cfg.get("kommo.subdomain", "") or "").strip()
    if not sub:
        return ""
    if sub.startswith("http"):
        return sub.rstrip("/")
    return f"https://{sub}.kommo.com"


def _kommo_token() -> str:
    return cfg.get_secret("kommo.token") or ""


def kommo_configured() -> bool:
    return bool(_kommo_base() and _kommo_token())


def ping_kommo() -> dict[str, Any]:
    base, token = _kommo_base(), _kommo_token()
    if not base or not token:
        return {"ok": False, "message": "Faltan kommo.subdomain / kommo.token."}
    url = f"{base}/api/v4/account"
    try:
        with httpx.Client(timeout=20.0) as client:
            res = client.get(url, headers={"Authorization": f"Bearer {token}"})
        if res.status_code < 300:
            return {"ok": True, "message": f"Kommo OK (HTTP {res.status_code}).", "status": res.status_code}
        return {
            "ok": False,
            "message": f"Kommo HTTP {res.status_code}: {res.text[:200]}",
            "status": res.status_code,
        }
    except Exception as exc:
        return {"ok": False, "message": f"Error conectando a Kommo: {exc}"}


def fetch_lead(lead_id: str) -> dict[str, Any]:
    base, token = _kommo_base(), _kommo_token()
    if not base or not token:
        raise ValueError("Kommo no configurado (subdomain/token).")
    url = f"{base}/api/v4/leads/{lead_id}"
    with httpx.Client(timeout=30.0) as client:
        res = client.get(
            url,
            params={"with": "contacts"},
            headers={"Authorization": f"Bearer {token}"},
        )
        IntegrationLog.objects.create(
            provider=IntegrationSource.KOMMO,
            method="GET",
            url=url,
            request_headers={"Authorization": "***REDACTED***"},
            request_body={"with": "contacts"},
            response_status=res.status_code,
            response_body={},
            latency_ms=0,
            success=res.status_code < 300,
            error="" if res.status_code < 300 else res.text[:500],
            ref_type="KommoLead",
            ref_id=str(lead_id),
        )
        res.raise_for_status()
        data = res.json()
        return data if isinstance(data, dict) else {}


def fetch_contact(contact_id: str) -> dict[str, Any]:
    base, token = _kommo_base(), _kommo_token()
    if not base or not token:
        raise ValueError("Kommo no configurado (subdomain/token).")
    url = f"{base}/api/v4/contacts/{contact_id}"
    with httpx.Client(timeout=30.0) as client:
        res = client.get(url, headers={"Authorization": f"Bearer {token}"})
        res.raise_for_status()
        data = res.json()
        return data if isinstance(data, dict) else {}


def enrich_from_webhook_payload(payload: dict) -> tuple[dict, dict | None]:
    """
    If payload already has enriched lead+contact, use them.
    Else extract lead_id from Kommo form webhook and fetch via API.
    """
    if isinstance(payload.get("lead"), dict) and payload["lead"].get("id"):
        lead = payload["lead"]
        contact = payload.get("contact") if isinstance(payload.get("contact"), dict) else None
        return lead, contact

    # Already looks like a lead object
    if payload.get("id") and payload.get("custom_fields_values") is not None:
        return payload, payload.get("contact") if isinstance(payload.get("contact"), dict) else None

    lead_id = (
        payload.get("leads[status][0][id]")
        or payload.get("lead_id")
        or ""
    )
    lead_id = str(lead_id).strip()
    if not lead_id or lead_id == "unknown":
        raise ValueError("Webhook Kommo sin lead_id")

    lead = fetch_lead(lead_id)
    contact = None
    # contacts embedded under _embedded.contacts
    embedded = (lead.get("_embedded") or {}).get("contacts") or []
    if embedded:
        cid = str(embedded[0].get("id") or "")
        if cid:
            contact = fetch_contact(cid)
    return lead, contact
