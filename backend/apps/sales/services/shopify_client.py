from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urljoin

import httpx
from django.core.cache import cache

from apps.config import settings_service as cfg
from apps.integrations.models import IntegrationLog, IntegrationSource

logger = logging.getLogger(__name__)

_TOKEN_CACHE_KEY = "shopify:admin_access_token:v1"


def _shop_domain() -> str:
    domain = (cfg.get("shopify.shop_domain", "") or "").strip()
    return domain.replace("https://", "").replace("http://", "").rstrip("/")


def _api_version() -> str:
    return (cfg.get("shopify.api_version", "2025-01") or "2025-01").strip()


def _legacy_static_token() -> str:
    return str(
        cfg.get_secret("shopify.admin_access_token")
        or cfg.get("shopify.admin_access_token", "")
        or ""
    )


def _client_id() -> str:
    return str(cfg.get("shopify.client_id", "") or "").strip()


def _client_secret() -> str:
    return str(
        cfg.get_secret("shopify.client_secret")
        or cfg.get("shopify.client_secret", "")
        or cfg.get_secret("shopify.api_secret")
        or ""
    )


def shopify_configured() -> bool:
    domain = _shop_domain()
    if not domain:
        return False
    if _legacy_static_token():
        return True
    return bool(_client_id() and _client_secret())


def _request_client_credentials_token(domain: str, client_id: str, client_secret: str) -> str:
    """
    Dev Dashboard apps: exchange Client ID/Secret for a short-lived Admin token.
    Docs: https://shopify.dev/docs/apps/build/dev-dashboard/get-api-access-tokens
    """
    url = f"https://{domain}/admin/oauth/access_token"
    with httpx.Client(timeout=20.0) as client:
        res = client.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if res.status_code >= 300:
        raise ValueError(
            f"Shopify token exchange HTTP {res.status_code}: {res.text[:240]}"
        )
    data = res.json() or {}
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise ValueError("Shopify token exchange sin access_token")
    expires_in = int(data.get("expires_in") or 86400)
    # Refresh 2 minutes early; cache payload with expiry epoch.
    ttl = max(60, expires_in - 120)
    cache.set(
        _TOKEN_CACHE_KEY,
        {"token": token, "expires_at": time.time() + expires_in},
        timeout=ttl,
    )
    return token


def get_admin_access_token(*, force_refresh: bool = False) -> str:
    """
    Resolve Admin API token.
    Preference: legacy static shpat_ → client_credentials (Dev Dashboard).
    """
    static = _legacy_static_token()
    if static:
        return static

    domain = _shop_domain()
    client_id = _client_id()
    client_secret = _client_secret()
    if not (domain and client_id and client_secret):
        return ""

    if not force_refresh:
        cached = cache.get(_TOKEN_CACHE_KEY)
        if isinstance(cached, dict):
            token = str(cached.get("token") or "")
            expires_at = float(cached.get("expires_at") or 0)
            if token and time.time() < expires_at - 60:
                return token

    return _request_client_credentials_token(domain, client_id, client_secret)


def _shopify_creds() -> tuple[str, str, str]:
    domain = _shop_domain()
    version = _api_version()
    try:
        token = get_admin_access_token()
    except Exception as exc:
        logger.warning("Shopify access token unavailable: %s", exc)
        token = ""
    return domain, token, version


def _base_url(domain: str, version: str) -> str:
    return f"https://{domain}/admin/api/{version}/"


def ping_shopify() -> dict[str, Any]:
    domain = _shop_domain()
    if not domain:
        return {"ok": False, "message": "Falta shopify.shop_domain (ej. tienda.myshopify.com)."}
    if not shopify_configured():
        return {
            "ok": False,
            "message": (
                "Faltan credenciales: Client ID + Client secret "
                "(Dev Dashboard) o Admin API access token legacy (shpat_)."
            ),
        }
    try:
        token = get_admin_access_token(force_refresh=True)
    except Exception as exc:
        return {"ok": False, "message": f"No se pudo obtener access token: {exc}"}
    if not token:
        return {"ok": False, "message": "Access token vacío."}

    version = _api_version()
    url = urljoin(_base_url(domain, version), "shop.json")
    try:
        with httpx.Client(timeout=20.0) as client:
            res = client.get(url, headers={"X-Shopify-Access-Token": token})
        if res.status_code < 300:
            shop = (res.json() or {}).get("shop") or {}
            name = shop.get("name") or domain
            mode = "legacy token" if _legacy_static_token() else "client_credentials"
            return {
                "ok": True,
                "message": f"Shopify OK · {name} ({mode}, HTTP {res.status_code}).",
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
            response_body={
                "count": len((res.json() or {}).get("orders") or []) if res.status_code < 300 else {}
            },
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
        raise ValueError(
            "Shopify no configurado (shop_domain + Client ID/Secret o token legacy)."
        )
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
