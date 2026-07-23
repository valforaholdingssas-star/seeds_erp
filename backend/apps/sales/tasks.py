from __future__ import annotations

import hashlib
import hmac
import logging

from celery import shared_task
from django.db import IntegrityError
from django.utils import timezone

from apps.config import settings_service as cfg
from apps.integrations.models import IntegrationSource, RawEventStatus, RawWebhookEvent
from apps.sales.services.kommo import upsert_kommo_from_enriched
from apps.sales.services.kommo_client import enrich_from_webhook_payload, kommo_configured
from apps.sales.services.woocommerce import upsert_ecommerce_from_payload

logger = logging.getLogger(__name__)


def persist_raw_event(
    *,
    source: str,
    event_type: str,
    payload: dict,
    headers: dict | None = None,
    signature: str = "",
    dedupe_key: str,
) -> tuple[RawWebhookEvent, bool]:
    """Returns (event, created). Duplicate dedupe_key → existing event, created=False."""
    try:
        event = RawWebhookEvent.objects.create(
            source=source,
            event_type=event_type,
            payload=payload,
            headers=headers or {},
            signature=signature or "",
            dedupe_key=dedupe_key,
            status=RawEventStatus.RECEIVED,
        )
        return event, True
    except IntegrityError:
        event = RawWebhookEvent.objects.get(dedupe_key=dedupe_key)
        return event, False


def verify_woo_signature(raw_body: bytes, signature: str) -> bool:
    secret = cfg.get_secret("woocommerce.webhook_secret") or ""
    if not secret:
        # Strict by default: reject unsigned when secret is missing.
        # Local/dev override: set woocommerce.require_signature=false.
        return not cfg.get_bool("woocommerce.require_signature", True)
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature or "")


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def process_raw_event(self, event_id: str):
    event = RawWebhookEvent.objects.filter(id=event_id).first()
    if not event:
        return
    try:
        if event.source == IntegrationSource.WOOCOMMERCE:
            upsert_ecommerce_from_payload(event.payload, raw_event=event)
        elif event.source == IntegrationSource.KOMMO:
            # Guard early on webhook status_id / pipeline_id (before enrich)
            won_status = str(cfg.get("kommo.won_status_id") or "")
            won_pipeline = str(cfg.get("kommo.won_pipeline_id") or "")
            raw_status = str(
                event.payload.get("leads[status][0][status_id]")
                or event.payload.get("status_id")
                or (event.payload.get("lead") or {}).get("status_id")
                or ""
            )
            raw_pipeline = str(
                event.payload.get("leads[status][0][pipeline_id]")
                or event.payload.get("pipeline_id")
                or (event.payload.get("lead") or {}).get("pipeline_id")
                or ""
            )
            if won_pipeline and raw_pipeline and raw_pipeline != won_pipeline:
                event.status = RawEventStatus.IGNORED
                event.error = f"pipeline_id {raw_pipeline} != won {won_pipeline}"
                event.processed_at = timezone.now()
                event.save(update_fields=["status", "error", "processed_at", "updated_at"])
                return
            if won_status and raw_status and raw_status != won_status:
                event.status = RawEventStatus.IGNORED
                event.error = f"status_id {raw_status} != won {won_status}"
                event.processed_at = timezone.now()
                event.save(update_fields=["status", "error", "processed_at", "updated_at"])
                return

            # Enrich via Kommo API when payload is form-webhook (ids only)
            try:
                lead, contact = enrich_from_webhook_payload(event.payload)
            except ValueError:
                # Fallback: treat payload as already-enriched lead
                if not kommo_configured() and isinstance(event.payload.get("lead"), dict):
                    lead, contact = event.payload["lead"], event.payload.get("contact")
                else:
                    raise

            # Trust the webhook status/pipeline guards above. The lead may have
            # moved to another column since the event (common on reprocess).
            upsert_kommo_from_enriched(lead=lead, contact=contact, raw_event=event)
        else:
            event.status = RawEventStatus.IGNORED
            event.error = f"Source no soportado en sales: {event.source}"
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error", "processed_at", "updated_at"])
            return

        event.status = RawEventStatus.PROCESSED
        event.error = ""
        event.processed_at = timezone.now()
        event.attempts = (event.attempts or 0) + 1
        event.save(
            update_fields=["status", "error", "processed_at", "attempts", "updated_at"]
        )
    except Exception as exc:
        logger.exception("process_raw_event failed %s", event_id)
        event.status = RawEventStatus.FAILED
        event.error = str(exc)
        event.attempts = (event.attempts or 0) + 1
        event.save(update_fields=["status", "error", "attempts", "updated_at"])
        raise self.retry(exc=exc)


@shared_task
def run_woo_resync_item(batch_id: str, item_id: str):
    from django.db import transaction

    from apps.logistics.models import BatchItemStatus, BatchJob, BatchJobStatus
    from apps.sales.services.resync import process_woo_resync_item

    with transaction.atomic():
        batch = BatchJob.objects.select_for_update().get(id=batch_id)
        item = batch.items.select_for_update().get(id=item_id)
        if item.status not in {BatchItemStatus.PENDING, BatchItemStatus.FAILED}:
            return
        item.status = BatchItemStatus.RUNNING
        item.save(update_fields=["status", "updated_at"])
        batch.status = BatchJobStatus.RUNNING
        batch.save(update_fields=["status", "updated_at"])

    try:
        result = process_woo_resync_item(order_id=item.ref_id)
        item.status = BatchItemStatus.SUCCESS
        item.result = result
        item.error = ""
    except Exception as exc:
        item.status = BatchItemStatus.FAILED
        item.error = str(exc)[:2000]
        item.result = {}
    item.save(update_fields=["status", "result", "error", "updated_at"])

    with transaction.atomic():
        batch = BatchJob.objects.select_for_update().get(id=batch_id)
        batch.done = batch.items.exclude(status=BatchItemStatus.PENDING).exclude(
            status=BatchItemStatus.RUNNING
        ).count()
        batch.success = batch.items.filter(status=BatchItemStatus.SUCCESS).count()
        batch.failed = batch.items.filter(status=BatchItemStatus.FAILED).count()
        if batch.done >= batch.total:
            batch.status = BatchJobStatus.COMPLETED
        batch.save(update_fields=["done", "success", "failed", "status", "updated_at"])


@shared_task
def enqueue_woo_resync(batch_id: str):
    from apps.logistics.models import BatchItemStatus, BatchJob

    batch = BatchJob.objects.get(id=batch_id)
    for item_id in batch.items.filter(status=BatchItemStatus.PENDING).order_by("created_at").values_list(
        "id", flat=True
    ):
        run_woo_resync_item(str(batch_id), str(item_id))
