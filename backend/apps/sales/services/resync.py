from __future__ import annotations

from urllib.parse import urljoin

import httpx

from apps.logistics.models import BatchItemStatus, BatchJob, BatchJobStatus, BatchJobType, BatchJobItem
from apps.sales.services.shopify import upsert_shopify_from_payload
from apps.sales.services.shopify_client import (
    fetch_order,
    iter_orders_in_range as iter_shopify_orders,
    shopify_configured,
)
from apps.sales.services.woo_client import _woo_creds, iter_orders_in_range, woo_configured
from apps.sales.services.woocommerce import upsert_ecommerce_from_payload


def start_woo_resync(
    *,
    after: str,
    before: str,
    status: str | None = None,
    actor=None,
) -> BatchJob:
    order_ids: list[str] = []
    if woo_configured():
        for order in iter_orders_in_range(after=after, before=before, status=status):
            oid = str(order.get("id") or "")
            if oid:
                order_ids.append(oid)

    batch = BatchJob.objects.create(
        job_type=BatchJobType.WOO_RESYNC,
        status=BatchJobStatus.PENDING if order_ids else BatchJobStatus.COMPLETED,
        total=len(order_ids),
        created_by=actor,
        meta={
            "after": after,
            "before": before,
            "status": status or "",
            "woo_configured": woo_configured(),
        },
    )
    BatchJobItem.objects.bulk_create(
        [
            BatchJobItem(
                batch=batch,
                ref_type="WooOrder",
                ref_id=oid,
                status=BatchItemStatus.PENDING,
            )
            for oid in order_ids
        ]
    )
    return batch


def process_woo_resync_item(*, order_id: str) -> dict:
    store, key, secret = _woo_creds()
    if not store.strip("/") or not key or not secret:
        raise ValueError("WooCommerce no configurado (store_url / keys).")
    url = urljoin(store, f"wp-json/wc/v3/orders/{order_id}")
    with httpx.Client(timeout=45.0, auth=(key, secret)) as client:
        res = client.get(url)
        res.raise_for_status()
        order = res.json()
    sale = upsert_ecommerce_from_payload(order)
    return {
        "order_id": order_id,
        "status": getattr(sale, "status", None),
        "external_id": getattr(sale, "external_id", order_id),
    }


def start_shopify_resync(
    *,
    after: str,
    before: str,
    financial_status: str | None = None,
    actor=None,
) -> BatchJob:
    order_ids: list[str] = []
    if shopify_configured():
        for order in iter_shopify_orders(
            after=after, before=before, financial_status=financial_status
        ):
            oid = str(order.get("id") or "")
            if oid:
                order_ids.append(oid)

    batch = BatchJob.objects.create(
        job_type=BatchJobType.SHOPIFY_RESYNC,
        status=BatchJobStatus.PENDING if order_ids else BatchJobStatus.COMPLETED,
        total=len(order_ids),
        created_by=actor,
        meta={
            "after": after,
            "before": before,
            "financial_status": financial_status or "",
            "shopify_configured": shopify_configured(),
        },
    )
    BatchJobItem.objects.bulk_create(
        [
            BatchJobItem(
                batch=batch,
                ref_type="ShopifyOrder",
                ref_id=oid,
                status=BatchItemStatus.PENDING,
            )
            for oid in order_ids
        ]
    )
    return batch


def process_shopify_resync_item(*, order_id: str) -> dict:
    order = fetch_order(order_id)
    sale = upsert_shopify_from_payload(order)
    return {
        "order_id": order_id,
        "status": getattr(sale, "status", None),
        "external_id": getattr(sale, "external_id", order_id),
    }
