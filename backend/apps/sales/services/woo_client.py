from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import httpx

from apps.config import settings_service as cfg
from apps.integrations.models import IntegrationLog, IntegrationSource

logger = logging.getLogger(__name__)


def _woo_creds() -> tuple[str, str, str]:
    store = (cfg.get("woocommerce.store_url", "") or "").rstrip("/") + "/"
    key = cfg.get_secret("woocommerce.consumer_key") or cfg.get("woocommerce.consumer_key", "") or ""
    secret = cfg.get_secret("woocommerce.consumer_secret") or ""
    return str(store), str(key), str(secret)


def woo_configured() -> bool:
    store, key, secret = _woo_creds()
    return bool(store.strip("/") and key and secret)


def ping_woocommerce() -> dict[str, Any]:
    store, key, secret = _woo_creds()
    if not store.strip("/") or not key or not secret:
        return {"ok": False, "message": "Faltan store_url / consumer_key / consumer_secret."}
    url = urljoin(store, "wp-json/wc/v3/system_status")
    try:
        with httpx.Client(timeout=20.0, auth=(key, secret)) as client:
            # system_status may 401 on some stores; fallback to orders?per_page=1
            res = client.get(urljoin(store, "wp-json/wc/v3/orders"), params={"per_page": 1})
        if res.status_code < 300:
            return {"ok": True, "message": f"WooCommerce OK (HTTP {res.status_code}).", "status": res.status_code}
        return {
            "ok": False,
            "message": f"WooCommerce respondió HTTP {res.status_code}: {res.text[:200]}",
            "status": res.status_code,
        }
    except Exception as exc:
        return {"ok": False, "message": f"Error conectando a WooCommerce: {exc}"}


def fetch_orders(
    *,
    after: str,
    before: str,
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> list[dict[str, Any]]:
    """
    GET /wp-json/wc/v3/orders?after=&before=
    Dates ISO8601. If credentials missing, returns [] (caller may mock).
    """
    store, key, secret = _woo_creds()
    if not store.strip("/") or not key or not secret:
        return []
    params: dict[str, Any] = {
        "after": after if "T" in after else f"{after}T00:00:00",
        "before": before if "T" in before else f"{before}T23:59:59",
        "page": page,
        "per_page": per_page,
        "orderby": "date",
        "order": "asc",
    }
    if status:
        params["status"] = status
    url = urljoin(store, "wp-json/wc/v3/orders")
    with httpx.Client(timeout=45.0, auth=(key, secret)) as client:
        res = client.get(url, params=params)
        IntegrationLog.objects.create(
            provider=IntegrationSource.WOOCOMMERCE,
            method="GET",
            url=str(res.request.url),
            request_headers={"Authorization": "***REDACTED***"},
            request_body=params,
            response_status=res.status_code,
            response_body={"count": len(res.json()) if res.status_code < 300 else {}},
            latency_ms=0,
            success=res.status_code < 300,
            error="" if res.status_code < 300 else res.text[:500],
            ref_type="WooResync",
            ref_id=f"{after}:{before}:{page}",
        )
        res.raise_for_status()
        data = res.json()
        return data if isinstance(data, list) else []


def iter_orders_in_range(*, after: str, before: str, status: str | None = None):
    page = 1
    while True:
        batch = fetch_orders(after=after, before=before, status=status, page=page, per_page=50)
        if not batch:
            break
        yield from batch
        if len(batch) < 50:
            break
        page += 1
        if page > 200:
            break
