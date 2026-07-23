from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.logistics.models import (
    BatchItemStatus,
    BatchJob,
    BatchJobStatus,
    BatchJobType,
)
from apps.logistics.services.formatting import format_shipment
from apps.logistics.services.shipments import generate_shipment_guide, mark_shipments_sent


@shared_task
def run_generate_shipment_item(batch_id: str, item_id: str, actor_id: str | None = None):
    from apps.users.models import User

    actor = User.objects.filter(id=actor_id).first() if actor_id else None
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
        shipment = generate_shipment_guide(item.ref_id, actor=actor)
        ok = bool(shipment.tracking_number)
        item.status = BatchItemStatus.SUCCESS if ok else BatchItemStatus.FAILED
        item.result = {
            "tracking_number": shipment.tracking_number,
            "status": shipment.status,
            "shipping_cost": str(shipment.shipping_cost) if shipment.shipping_cost is not None else None,
            "label_url": shipment.label_url,
            "warning": shipment.warning,
        }
        item.error = "" if ok else (shipment.last_error or "Sin guía")
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
def enqueue_generate_shipments(batch_id: str, actor_id: str | None = None):
    """Process items sequentially (one Celery task chaining the next)."""
    batch = BatchJob.objects.get(id=batch_id)
    pending = list(
        batch.items.filter(status=BatchItemStatus.PENDING).order_by("created_at").values_list(
            "id", flat=True
        )
    )
    for item_id in pending:
        run_generate_shipment_item(str(batch_id), str(item_id), actor_id)


@shared_task
def run_format_batch(batch_id: str):
    from apps.logistics.models import Shipment

    batch = BatchJob.objects.get(id=batch_id)
    batch.status = BatchJobStatus.RUNNING
    batch.save(update_fields=["status", "updated_at"])
    for item in batch.items.filter(status=BatchItemStatus.PENDING):
        item.status = BatchItemStatus.RUNNING
        item.save(update_fields=["status", "updated_at"])
        try:
            shipment = Shipment.objects.get(id=item.ref_id)
            format_shipment(shipment)
            item.status = BatchItemStatus.SUCCESS
            item.result = {
                "address_formatted": shipment.address_formatted,
                "geo_state_code": shipment.geo_state_code,
                "do_not_ship": shipment.do_not_ship,
                "status": shipment.status,
            }
            item.error = ""
        except Exception as exc:
            item.status = BatchItemStatus.FAILED
            item.error = str(exc)[:2000]
        item.save(update_fields=["status", "result", "error", "updated_at"])
        batch.done += 1
        if item.status == BatchItemStatus.SUCCESS:
            batch.success += 1
        else:
            batch.failed += 1
        batch.save(update_fields=["done", "success", "failed", "updated_at"])
    batch.status = BatchJobStatus.COMPLETED
    batch.save(update_fields=["status", "updated_at"])
