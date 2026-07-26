from __future__ import annotations

from celery import shared_task
from django.db import transaction

from apps.logistics.models import (
    BatchItemStatus,
    BatchJob,
    BatchJobStatus,
    BatchJobType,
)


# Reuse logistics BatchJob with a dedicated type string stored in meta if needed.
# Add ACCOUNTING_ISSUE to BatchJobType via using GENERATE pattern in meta.


@shared_task
def run_issue_invoice_item(batch_id: str, item_id: str, actor_id: str | None = None):
    from apps.accounting.services.invoicing import issue_invoice
    from apps.users.models import User

    actor = User.objects.filter(id=actor_id).first() if actor_id else None
    with transaction.atomic():
        batch = BatchJob.objects.select_for_update().get(id=batch_id)
        item = batch.items.select_for_update().get(id=item_id)
        item.status = BatchItemStatus.RUNNING
        item.save(update_fields=["status", "updated_at"])
        batch.status = BatchJobStatus.RUNNING
        batch.save(update_fields=["status", "updated_at"])

    try:
        invoice = issue_invoice(item.ref_id, actor=actor)
        ok = invoice.status == "GENERADA"
        item.status = BatchItemStatus.SUCCESS if ok else BatchItemStatus.FAILED
        item.result = {
            "status": invoice.status,
            "number": invoice.number,
            "alegra_id": invoice.alegra_id,
            "pdf_url": invoice.pdf_url,
        }
        item.error = "" if ok else (invoice.last_error or "Fallida")
    except Exception as exc:
        item.status = BatchItemStatus.FAILED
        item.error = str(exc)[:2000]
        item.result = {}
    item.save(update_fields=["status", "result", "error", "updated_at"])

    with transaction.atomic():
        batch = BatchJob.objects.select_for_update().get(id=batch_id)
        batch.done = batch.items.exclude(status__in=[BatchItemStatus.PENDING, BatchItemStatus.RUNNING]).count()
        batch.success = batch.items.filter(status=BatchItemStatus.SUCCESS).count()
        batch.failed = batch.items.filter(status=BatchItemStatus.FAILED).count()
        if batch.done >= batch.total:
            batch.status = BatchJobStatus.COMPLETED
        batch.save(update_fields=["done", "success", "failed", "status", "updated_at"])


@shared_task
def enqueue_issue_invoices(batch_id: str, actor_id: str | None = None):
    batch = BatchJob.objects.get(id=batch_id)
    pending = list(
        batch.items.filter(status=BatchItemStatus.PENDING)
        .order_by("created_at")
        .values_list("id", flat=True)
    )
    for item_id in pending:
        run_issue_invoice_item(str(batch_id), str(item_id), actor_id)


@shared_task
def run_sync_customer_item(batch_id: str, item_id: str, actor_id: str | None = None):
    from apps.accounting.models import Customer
    from apps.accounting.services.invoicing import sync_customer_to_alegra
    from apps.users.models import User

    actor = User.objects.filter(id=actor_id).first() if actor_id else None
    with transaction.atomic():
        batch = BatchJob.objects.select_for_update().get(id=batch_id)
        item = batch.items.select_for_update().get(id=item_id)
        item.status = BatchItemStatus.RUNNING
        item.save(update_fields=["status", "updated_at"])
        batch.status = BatchJobStatus.RUNNING
        batch.save(update_fields=["status", "updated_at"])

    try:
        customer = Customer.objects.get(id=item.ref_id)
        customer = sync_customer_to_alegra(customer, actor=actor)
        ok = bool(customer.alegra_synced and customer.alegra_id)
        item.status = BatchItemStatus.SUCCESS if ok else BatchItemStatus.FAILED
        item.result = {
            "name": customer.name,
            "alegra_id": customer.alegra_id,
            "id_number": customer.id_number,
            "status": "SYNCED" if ok else "NO_ID",
        }
        item.error = "" if ok else "Alegra no devolvió id de contacto"
    except Exception as exc:
        item.status = BatchItemStatus.FAILED
        item.error = str(exc)[:2000]
        if not isinstance(item.result, dict):
            item.result = {}
    item.save(update_fields=["status", "result", "error", "updated_at"])

    with transaction.atomic():
        batch = BatchJob.objects.select_for_update().get(id=batch_id)
        batch.done = batch.items.exclude(
            status__in=[BatchItemStatus.PENDING, BatchItemStatus.RUNNING]
        ).count()
        batch.success = batch.items.filter(status=BatchItemStatus.SUCCESS).count()
        batch.failed = batch.items.filter(status=BatchItemStatus.FAILED).count()
        if batch.done >= batch.total:
            batch.status = BatchJobStatus.COMPLETED
        batch.save(update_fields=["done", "success", "failed", "status", "updated_at"])


@shared_task
def enqueue_sync_customers(batch_id: str, actor_id: str | None = None):
    batch = BatchJob.objects.get(id=batch_id)
    pending = list(
        batch.items.filter(status=BatchItemStatus.PENDING)
        .order_by("created_at")
        .values_list("id", flat=True)
    )
    for item_id in pending:
        run_sync_customer_item(str(batch_id), str(item_id), actor_id)
