from __future__ import annotations

import json
import logging
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.config import settings_service as cfg

logger = logging.getLogger(__name__)


def _dec(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dt(value) -> str | None:
    if not value:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return value.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")


def bigquery_configured() -> bool:
    if not cfg.get_bool("bigquery.enabled", False):
        return False
    project = (cfg.get("bigquery.project_id", "") or "").strip()
    creds = cfg.get_secret("bigquery.credentials_json") or ""
    return bool(project and creds.strip())


def _client():
    from google.cloud import bigquery
    from google.oauth2 import service_account

    raw = cfg.get_secret("bigquery.credentials_json") or ""
    info = json.loads(raw)
    credentials = service_account.Credentials.from_service_account_info(info)
    project = (cfg.get("bigquery.project_id", "") or "").strip()
    return bigquery.Client(project=project, credentials=credentials)


def _ensure_dataset(client) -> str:
    from google.cloud import bigquery

    project = (cfg.get("bigquery.project_id", "") or "").strip()
    dataset_id = (cfg.get("bigquery.dataset_id", "seeds_erp") or "seeds_erp").strip()
    location = (cfg.get("bigquery.location", "us") or "us").strip()
    dataset_ref = f"{project}.{dataset_id}"
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = location
    client.create_dataset(dataset, exists_ok=True)
    return dataset_ref


def _load_rows(client, table_id: str, rows: list[dict[str, Any]], schema: list) -> int:
    from google.cloud import bigquery

    table = bigquery.Table(table_id, schema=schema)
    client.create_table(table, exists_ok=True)

    if not rows:
        client.query(f"TRUNCATE TABLE `{table_id}`").result()
        return 0

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    chunk_size = 1000
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        job_config.write_disposition = (
            bigquery.WriteDisposition.WRITE_TRUNCATE
            if i == 0
            else bigquery.WriteDisposition.WRITE_APPEND
        )
        job = client.load_table_from_json(chunk, table_id, job_config=job_config)
        job.result()
        total += len(chunk)
    return total


def _sales_rows() -> list[dict[str, Any]]:
    from apps.sales.models import ConsolidatedSale

    rows: list[dict[str, Any]] = []
    qs = (
        ConsolidatedSale.objects.select_related("seller", "payment_method")
        .order_by("created_at")
        .iterator(chunk_size=500)
    )
    for s in qs:
        rows.append(
            {
                "id": str(s.id),
                "source": s.source,
                "external_id": s.external_id,
                "state": s.state,
                "status": s.status,
                "seller_id": str(s.seller_id) if s.seller_id else None,
                "seller_name": s.seller.name if s.seller_id else None,
                "customer_name": s.customer_name or None,
                "email": s.email or None,
                "phone": s.phone or None,
                "id_number": s.id_number or None,
                "city": s.city_raw or None,
                "state_raw": s.state_raw or None,
                "amount_products": _dec(s.amount_products),
                "amount_shipping": _dec(s.amount_shipping),
                "total_value": _dec(s.total_value),
                "iva_generated": _dec(s.iva_generated),
                "net_value": _dec(s.net_value),
                "payment_account": s.payment_account or None,
                "payment_method": (
                    s.payment_method.name if s.payment_method_id else None
                ),
                "income_source": s.income_source or None,
                "fulfillment_type": s.fulfillment_type,
                "requires_shipping": bool(s.requires_shipping),
                "closed_at": _dt(s.closed_at),
                "created_at": _dt(s.created_at),
                "updated_at": _dt(s.updated_at),
                "synced_at": _dt(timezone.now()),
            }
        )
    return rows


def _sale_item_rows() -> list[dict[str, Any]]:
    from apps.sales.models import SaleItem

    rows: list[dict[str, Any]] = []
    qs = SaleItem.objects.select_related("sale").order_by("created_at").iterator(
        chunk_size=500
    )
    for it in qs:
        rows.append(
            {
                "id": str(it.id),
                "sale_id": str(it.sale_id),
                "sale_external_id": it.sale.external_id if it.sale_id else None,
                "sale_source": it.sale.source if it.sale_id else None,
                "color": it.color,
                "tipo": it.tipo or None,
                "quantity": int(it.quantity or 0),
                "woo_product_id": it.woo_product_id or None,
                "product_name": it.product_name or None,
                "synced_at": _dt(timezone.now()),
            }
        )
    return rows


def _shipment_rows() -> list[dict[str, Any]]:
    from apps.logistics.models import Shipment

    rows: list[dict[str, Any]] = []
    qs = (
        Shipment.objects.select_related("sale")
        .order_by("created_at")
        .iterator(chunk_size=500)
    )
    for sh in qs:
        rows.append(
            {
                "id": str(sh.id),
                "sale_id": str(sh.sale_id),
                "sale_external_id": sh.sale.external_id if sh.sale_id else None,
                "status": sh.status,
                "carrier": sh.carrier or None,
                "tracking_number": sh.tracking_number or None,
                "city": sh.city_mirror or sh.generated_city or None,
                "state": sh.state_mirror or sh.generated_state or None,
                "shipping_cost": _dec(sh.shipping_cost),
                "do_not_ship": bool(sh.do_not_ship),
                "warning": bool(sh.warning),
                "sent_at": _dt(sh.sent_at),
                "created_at": _dt(sh.created_at),
                "updated_at": _dt(sh.updated_at),
                "synced_at": _dt(timezone.now()),
            }
        )
    return rows


def ping_bigquery() -> dict[str, Any]:
    if not bigquery_configured():
        return {
            "ok": False,
            "message": "Activa bigquery.enabled y configura project_id + credentials_json.",
        }
    try:
        client = _client()
        dataset_ref = _ensure_dataset(client)
        list(client.list_tables(dataset_ref, max_results=1))
        return {"ok": True, "message": f"BigQuery OK · dataset {dataset_ref}"}
    except Exception as exc:
        return {"ok": False, "message": f"Error BigQuery: {exc}"[:400]}


def sync_analytics_to_bigquery() -> dict[str, Any]:
    """
    Full refresh of reporting tables into BigQuery (small data → cheap & simple).
    Safe to run nightly on a small EC2.
    """
    if not bigquery_configured():
        return {
            "ok": False,
            "skipped": True,
            "message": "BigQuery deshabilitado o sin project_id / credentials_json.",
        }

    from google.cloud import bigquery

    started = timezone.now()
    client = _client()
    dataset_ref = _ensure_dataset(client)

    sales_schema = [
        bigquery.SchemaField("id", "STRING"),
        bigquery.SchemaField("source", "STRING"),
        bigquery.SchemaField("external_id", "STRING"),
        bigquery.SchemaField("state", "STRING"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("seller_id", "STRING"),
        bigquery.SchemaField("seller_name", "STRING"),
        bigquery.SchemaField("customer_name", "STRING"),
        bigquery.SchemaField("email", "STRING"),
        bigquery.SchemaField("phone", "STRING"),
        bigquery.SchemaField("id_number", "STRING"),
        bigquery.SchemaField("city", "STRING"),
        bigquery.SchemaField("state_raw", "STRING"),
        bigquery.SchemaField("amount_products", "FLOAT64"),
        bigquery.SchemaField("amount_shipping", "FLOAT64"),
        bigquery.SchemaField("total_value", "FLOAT64"),
        bigquery.SchemaField("iva_generated", "FLOAT64"),
        bigquery.SchemaField("net_value", "FLOAT64"),
        bigquery.SchemaField("payment_account", "STRING"),
        bigquery.SchemaField("payment_method", "STRING"),
        bigquery.SchemaField("income_source", "STRING"),
        bigquery.SchemaField("fulfillment_type", "STRING"),
        bigquery.SchemaField("requires_shipping", "BOOL"),
        bigquery.SchemaField("closed_at", "TIMESTAMP"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
        bigquery.SchemaField("updated_at", "TIMESTAMP"),
        bigquery.SchemaField("synced_at", "TIMESTAMP"),
    ]
    items_schema = [
        bigquery.SchemaField("id", "STRING"),
        bigquery.SchemaField("sale_id", "STRING"),
        bigquery.SchemaField("sale_external_id", "STRING"),
        bigquery.SchemaField("sale_source", "STRING"),
        bigquery.SchemaField("color", "STRING"),
        bigquery.SchemaField("tipo", "STRING"),
        bigquery.SchemaField("quantity", "INT64"),
        bigquery.SchemaField("woo_product_id", "STRING"),
        bigquery.SchemaField("product_name", "STRING"),
        bigquery.SchemaField("synced_at", "TIMESTAMP"),
    ]
    shipments_schema = [
        bigquery.SchemaField("id", "STRING"),
        bigquery.SchemaField("sale_id", "STRING"),
        bigquery.SchemaField("sale_external_id", "STRING"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("carrier", "STRING"),
        bigquery.SchemaField("tracking_number", "STRING"),
        bigquery.SchemaField("city", "STRING"),
        bigquery.SchemaField("state", "STRING"),
        bigquery.SchemaField("shipping_cost", "FLOAT64"),
        bigquery.SchemaField("do_not_ship", "BOOL"),
        bigquery.SchemaField("warning", "BOOL"),
        bigquery.SchemaField("sent_at", "TIMESTAMP"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
        bigquery.SchemaField("updated_at", "TIMESTAMP"),
        bigquery.SchemaField("synced_at", "TIMESTAMP"),
    ]

    sales = _sales_rows()
    items = _sale_item_rows()
    shipments = _shipment_rows()

    n_sales = _load_rows(client, f"{dataset_ref}.fact_sales", sales, sales_schema)
    n_items = _load_rows(
        client, f"{dataset_ref}.fact_sale_items", items, items_schema
    )
    n_ship = _load_rows(
        client, f"{dataset_ref}.fact_shipments", shipments, shipments_schema
    )

    elapsed = (timezone.now() - started).total_seconds()
    result = {
        "ok": True,
        "skipped": False,
        "dataset": dataset_ref,
        "fact_sales": n_sales,
        "fact_sale_items": n_items,
        "fact_shipments": n_ship,
        "elapsed_seconds": round(elapsed, 2),
        "synced_at": _dt(timezone.now()),
    }
    logger.info("BigQuery sync OK %s", result)
    return result
