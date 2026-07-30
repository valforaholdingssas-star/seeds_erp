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


def migrate_woocommerce_webhooks(*, new_base: str | None = None) -> dict[str, Any]:
    """
    Rewrite WooCommerce webhook delivery URLs that still point at the Elastic IP
    to the public HTTPS base (erp.seedscol.com).
    """
    from apps.config.public_urls import public_base_url, rewrite_legacy_url

    store, key, secret = _woo_creds()
    if not store.strip("/") or not key or not secret:
        return {
            "ok": False,
            "message": "WooCommerce no configurado (store_url / keys).",
            "updated": [],
            "skipped": [],
            "errors": [],
        }

    root = (new_base or public_base_url()).rstrip("/")
    updated: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    errors: list[str] = []

    url = urljoin(store, "wp-json/wc/v3/webhooks")
    try:
        with httpx.Client(timeout=45.0, auth=(key, secret)) as client:
            page = 1
            while page <= 20:
                res = client.get(url, params={"per_page": 50, "page": page})
                if res.status_code >= 300:
                    return {
                        "ok": False,
                        "message": f"No se pudieron listar webhooks Woo (HTTP {res.status_code}).",
                        "updated": updated,
                        "skipped": skipped,
                        "errors": [res.text[:240]],
                    }
                rows = res.json()
                if not isinstance(rows, list) or not rows:
                    break
                for wh in rows:
                    wid = str(wh.get("id") or "")
                    delivery = str(wh.get("delivery_url") or "")
                    name = str(wh.get("name") or wid)
                    new_url = rewrite_legacy_url(delivery, root)
                    if not new_url:
                        skipped.append({"id": wid, "name": name, "url": delivery})
                        continue
                    patch = client.put(
                        urljoin(store, f"wp-json/wc/v3/webhooks/{wid}"),
                        json={"delivery_url": new_url},
                    )
                    if patch.status_code >= 300:
                        errors.append(f"{name} ({wid}): HTTP {patch.status_code}")
                        continue
                    updated.append(
                        {"id": wid, "name": name, "from": delivery, "to": new_url}
                    )
                if len(rows) < 50:
                    break
                page += 1
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Error migrando webhooks Woo: {exc}",
            "updated": updated,
            "skipped": skipped,
            "errors": errors + [str(exc)],
        }

    # Ensure Seeds endpoints exist (create if missing)
    desired = [
        ("Seeds ERP · order created", "order.created", f"{root}/api/v1/webhooks/woocommerce/order-created/"),
        ("Seeds ERP · order updated", "order.updated", f"{root}/api/v1/webhooks/woocommerce/order-updated/"),
    ]
    existing_urls = {s.get("url") for s in skipped} | {u.get("to") for u in updated}
    # refresh list of current delivery urls
    try:
        with httpx.Client(timeout=45.0, auth=(key, secret)) as client:
            res = client.get(url, params={"per_page": 100})
            current = res.json() if res.status_code < 300 and isinstance(res.json(), list) else []
            current_urls = {str(w.get("delivery_url") or "").rstrip("/") for w in current}
            for name, topic, delivery_url in desired:
                if delivery_url.rstrip("/") in current_urls:
                    continue
                created = client.post(
                    url,
                    json={
                        "name": name,
                        "topic": topic,
                        "delivery_url": delivery_url,
                        "status": "active",
                    },
                )
                if created.status_code < 300:
                    updated.append(
                        {
                            "id": str((created.json() or {}).get("id") or "new"),
                            "name": name,
                            "from": "",
                            "to": delivery_url,
                        }
                    )
                else:
                    errors.append(f"crear {topic}: HTTP {created.status_code} {created.text[:160]}")
    except Exception as exc:
        errors.append(f"ensure create: {exc}")

    ok = len(errors) == 0
    return {
        "ok": ok,
        "message": (
            f"Woo webhooks: actualizados {len(updated)}, "
            f"sin cambio {len(skipped)}, errores {len(errors)}."
        ),
        "public_base_url": root,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }
