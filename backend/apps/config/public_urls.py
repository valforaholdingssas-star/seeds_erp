"""Public ERP base URL and inbound webhook catalog."""

from __future__ import annotations

from apps.config import settings_service as cfg

DEFAULT_PUBLIC_BASE_URL = "https://erp.seedscol.com"
LEGACY_PUBLIC_HOSTS = (
    "http://52.5.54.227",
    "https://52.5.54.227",
    "52.5.54.227",
)


def public_base_url() -> str:
    raw = (cfg.get("business.public_base_url", "") or "").strip()
    if not raw:
        raw = DEFAULT_PUBLIC_BASE_URL
    return raw.rstrip("/")


def webhook_catalog(base: str | None = None) -> list[dict[str, str]]:
    root = (base or public_base_url()).rstrip("/")
    return [
        {
            "provider": "WOOCOMMERCE",
            "topic": "order.created",
            "url": f"{root}/api/v1/webhooks/woocommerce/order-created/",
            "where": "WooCommerce → Webhooks, o plugin Seeds ERP → URL del ERP",
        },
        {
            "provider": "WOOCOMMERCE",
            "topic": "order.updated",
            "url": f"{root}/api/v1/webhooks/woocommerce/order-updated/",
            "where": "WooCommerce → Webhooks, o plugin Seeds ERP → URL del ERP",
        },
        {
            "provider": "SHOPIFY",
            "topic": "orders/*",
            "url": f"{root}/api/v1/webhooks/shopify/orders/",
            "where": "Shopify app webhooks (create/updated/paid/cancelled)",
        },
        {
            "provider": "KOMMO",
            "topic": "lead.status",
            "url": f"{root}/webhook/seeds-erp/",
            "where": "Kommo Digital Pipeline → URL del webhook (también vale /api/v1/webhooks/kommo/lead-status-changed/)",
        },
        {
            "provider": "KOMMO",
            "topic": "lead.status (API path)",
            "url": f"{root}/api/v1/webhooks/kommo/lead-status-changed/",
            "where": "Alternativa si Kommo acepta path /api/…",
        },
    ]


def is_legacy_delivery_url(url: str) -> bool:
    u = (url or "").strip().lower()
    return any(host in u for host in LEGACY_PUBLIC_HOSTS)


def rewrite_legacy_url(url: str, new_base: str | None = None) -> str | None:
    """If URL points at the old Elastic IP, rewrite to the new public base keeping the path."""
    raw = (url or "").strip()
    if not raw or not is_legacy_delivery_url(raw):
        return None
    root = (new_base or public_base_url()).rstrip("/")
    # Strip scheme+host
    path = raw
    for prefix in (
        "https://52.5.54.227",
        "http://52.5.54.227",
        "https://52.5.54.227/",
        "http://52.5.54.227/",
    ):
        if raw.lower().startswith(prefix.rstrip("/").lower()) or raw.lower().startswith(
            prefix.lower()
        ):
            path = raw[len(prefix.rstrip("/")) :]
            break
    else:
        # fallback: find first /
        idx = raw.find("/", raw.find("://") + 3) if "://" in raw else -1
        path = raw[idx:] if idx >= 0 else "/"
    if not path.startswith("/"):
        path = "/" + path
    return f"{root}{path}"
