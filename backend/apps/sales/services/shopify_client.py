from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import httpx

from apps.config import settings_service as cfg
from apps.integrations.models import IntegrationLog, IntegrationSource

logger = logging.getLogger(__name__)


def _shopify_creds() -> tuple[str, str, str]:
    domain = (cfg.get("shopify.shop_domain", "") or "").strip()
    domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
    token = (
        cfg.get_secret("shopify.admin_access_token")
        or cfg.get("shopify.admin_access_token", "")
        or ""
    )
    version = (cfg.get("shopify.api_version", "2025-01") or "2025-01").strip()
    return domain, str(token), version


def shopify_configured() -> bool:
    domain, token, _version = _shopify_creds()
    return bool(domain and token)


def _base_url(domain: str, version: str) -> str:
    return f"https://{domain}/admin/api/{version}/"


def ping_shopify() -> dict[str, Any]:
    domain, token, version = _shopify_creds()
    if not domain or not token:
        return {
            "ok": False,
            "message": "Faltan shopify.shop_domain / admin_access_token.",
        }
    url = urljoin(_base_url(domain, version), "shop.json")
    try:
        with httpx.Client(timeout=20.0) as client:
            res = client.get(url, headers={"X-Shopify-Access-Token": token})
        if res.status_code < 300:
            shop = (res.json() or {}).get("shop") or {}
            name = shop.get("name") or domain
            return {
                "ok": True,
                "message": f"Shopify OK · {name} (HTTP {res.status_code}).",
                "status": res.status_code,
            }
        return {
            "ok": False,
            "message": f"Shopify respondió HTTP {res.status_code}: {res.text[:200]}",
            "status": res.status_code,
        }
    except Exception as exc:
        return {"ok": False, "message": f"Error conectando a Shopify: {exc}"}


def fetch_orders(
    *,
    created_at_min: str,
    created_at_max: str,
    status: str | None = None,
    financial_status: str | None = None,
    limit: int = 50,
    page_info: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    GET /admin/api/{version}/orders.json
    Returns (orders, next_page_info).
    """
    domain, token, version = _shopify_creds()
    if not domain or not token:
        return [], None

    params: dict[str, Any] = {"limit": min(limit, 250), "status": status or "any"}
    if page_info:
        params = {"limit": min(limit, 250), "page_info": page_info}
    else:
        if created_at_min:
            params["created_at_min"] = (
                created_at_min if "T" in created_at_min else f"{created_at_min}T00:00:00-05:00"
            )
        if created_at_max:
            params["created_at_max"] = (
                created_at_max if "T" in created_at_max else f"{created_at_max}T23:59:59-05:00"
            )
        if financial_status:
            params["financial_status"] = financial_status

    url = urljoin(_base_url(domain, version), "orders.json")
    with httpx.Client(timeout=45.0) as client:
        res = client.get(
            url,
            params=params,
            headers={"X-Shopify-Access-Token": token},
        )
        IntegrationLog.objects.create(
            provider=IntegrationSource.SHOPIFY,
            method="GET",
            url=str(res.request.url),
            request_headers={"X-Shopify-Access-Token": "***REDACTED***"},
            request_body=params,
            response_status=res.status_code,
            response_body={"count": len((res.json() or {}).get("orders") or []) if res.status_code < 300 else {}},
            latency_ms=0,
            success=res.status_code < 300,
            error="" if res.status_code < 300 else res.text[:500],
            ref_type="ShopifyResync",
            ref_id=f"{created_at_min}:{created_at_max}",
        )
        res.raise_for_status()
        data = res.json() or {}
        orders = data.get("orders") if isinstance(data, dict) else []
        if not isinstance(orders, list):
            orders = []

        next_info = None
        link = res.headers.get("Link") or res.headers.get("link") or ""
        # Rel next page_info=...
        for part in link.split(","):
            if 'rel="next"' in part:
                if "page_info=" in part:
                    frag = part.split("page_info=")[1]
                    next_info = frag.split(">")[0].split("&")[0]
                break
        return orders, next_info


def fetch_order(order_id: str) -> dict[str, Any]:
    domain, token, version = _shopify_creds()
    if not domain or not token:
        raise ValueError("Shopify no configurado (shop_domain / admin_access_token).")
    url = urljoin(_base_url(domain, version), f"orders/{order_id}.json")
    with httpx.Client(timeout=45.0) as client:
        res = client.get(url, headers={"X-Shopify-Access-Token": token})
        res.raise_for_status()
        data = res.json() or {}
        order = data.get("order") if isinstance(data, dict) else None
        if not isinstance(order, dict):
            raise ValueError(f"Orden Shopify {order_id} sin payload")
        return order


def iter_orders_in_range(
    *,
    after: str,
    before: str,
    financial_status: str | None = None,
):
    page_info = None
    pages = 0
    while pages < 200:
        orders, page_info = fetch_orders(
            created_at_min=after,
            created_at_max=before,
            financial_status=financial_status,
            page_info=page_info,
        )
        if not orders:
            break
        yield from orders
        pages += 1
        if not page_info:
            break
