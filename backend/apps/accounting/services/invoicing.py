from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounting.models import Customer, Invoice, InvoiceStatus, Refund, RefundStatus
from apps.accounting.services import alegra as alegra_client
from apps.audit.services import log_audit_event
from apps.sales.models import SaleState
from apps.sales.services.normalization import withdraw_from_consolidated


def ensure_customer_from_sale(sale, *, actor=None) -> Customer:
    from apps.accounting.services.alegra import (
        _is_weak_person_name,
        _name_from_email,
        resolve_customer_display_name,
    )

    id_number = (sale.id_number or "").strip() or f"SIN-DOC-{sale.external_id}"
    # Normalize document early so get_or_create matches formatted CC/NIT.
    from apps.accounting.services.alegra import _digits_only

    digits = _digits_only(id_number)
    if digits and not id_number.upper().startswith("SIN-DOC"):
        id_number = digits

    raw_name = (sale.customer_name or "").strip()
    if _is_weak_person_name(raw_name, id_number=id_number):
        raw_name = _name_from_email(sale.email or "") or raw_name

    customer, created = Customer.objects.get_or_create(
        id_type="CC",
        id_number=id_number,
        defaults={
            "name": raw_name or id_number,
            "email": sale.email or "",
            "phone": sale.phone or "",
            "address": sale.address_raw or "",
            "city": sale.city_raw or "",
        },
    )
    if not created:
        # refresh soft fields
        changed = False
        for field, value in [
            ("name", raw_name or customer.name),
            ("email", sale.email or customer.email),
            ("phone", sale.phone or customer.phone),
            ("address", sale.address_raw or customer.address),
            ("city", sale.city_raw or customer.city),
        ]:
            if value and getattr(customer, field) != value:
                # Don't overwrite a good name with a weak Kommo lead-id.
                if field == "name" and _is_weak_person_name(
                    value, id_number=customer.id_number
                ):
                    continue
                if field == "name" and not _is_weak_person_name(
                    customer.name, id_number=customer.id_number
                ):
                    continue
                setattr(customer, field, value)
                changed = True
        healed = resolve_customer_display_name(customer)
        if healed != (customer.name or "").strip():
            customer.name = healed
            changed = True
        if changed:
            customer.save()
    else:
        healed = resolve_customer_display_name(customer)
        if healed != (customer.name or "").strip():
            customer.name = healed
            customer.save(update_fields=["name", "updated_at"])
    return customer


@transaction.atomic
def ensure_invoice_for_sale(sale, *, actor=None) -> Invoice | None:
    if hasattr(sale, "invoice"):
        return sale.invoice
    customer = ensure_customer_from_sale(sale, actor=actor)
    key = f"{sale.source}:{sale.external_id}"
    invoice, created = Invoice.objects.get_or_create(
        sale=sale,
        defaults={
            "customer": customer,
            "status": InvoiceStatus.POR_GENERAR,
            "total": sale.total_value,
            "iva": sale.iva_generated,
            "idempotency_key": key,
        },
    )
    if created:
        log_audit_event(
            actor=actor,
            action="INVOICE_QUEUED",
            entity="Invoice",
            entity_id=str(invoice.id),
            metadata={"key": key},
        )
    return invoice


@transaction.atomic
def sync_customer_to_alegra(customer: Customer, *, actor=None, force: bool = False) -> Customer:
    from apps.accounting.services.alegra import resolve_customer_display_name

    display = resolve_customer_display_name(customer)
    if display and display != (customer.name or "").strip():
        customer.name = display
        customer.save(update_fields=["name", "updated_at"])

    if customer.alegra_id and customer.alegra_synced and not force:
        # Re-push name/address so weak lead-id names get fixed on click.
        alegra_client.update_contact(customer)
        return customer
    if customer.alegra_id and not force:
        alegra_client.update_contact(customer)
        customer.alegra_synced = True
        customer.save(update_fields=["alegra_synced", "updated_at"])
        return customer
    body = alegra_client.create_or_find_contact(customer)
    alegra_id = str(body.get("id") or "").strip()
    if not alegra_id:
        raise RuntimeError(f"Alegra no devolvió id de contacto: {body}")
    customer.alegra_id = alegra_id
    customer.alegra_synced = True
    customer.save(update_fields=["alegra_id", "alegra_synced", "updated_at"])
    log_audit_event(
        actor=actor,
        action="CUSTOMER_SYNCED_ALEGRA",
        entity="Customer",
        entity_id=str(customer.id),
        metadata={"alegra_id": customer.alegra_id},
    )
    return customer


def bulk_sync_customers_to_alegra(ids: list, *, actor=None) -> dict:
    ok = 0
    errors: list[dict] = []
    for cid in ids:
        customer = Customer.objects.filter(id=cid).first()
        if not customer:
            errors.append({"id": str(cid), "detail": "Cliente no encontrado"})
            continue
        try:
            sync_customer_to_alegra(customer, actor=actor)
            ok += 1
        except Exception as exc:
            errors.append({"id": str(customer.id), "name": customer.name, "detail": str(exc)[:500]})
    return {"synced": ok, "failed": len(errors), "errors": errors}


def normalize_customer_documents(ids: list | None = None, *, actor=None) -> dict:
    """Strip non-digits from Customer.id_number (Alegra CO requires numeric docs).

    If ``ids`` is empty/None, processes every customer whose document still has
    non-digit characters. Skips unchanged rows; reports collisions and empty results.
    """
    qs = Customer.objects.all().order_by("created_at")
    if ids:
        qs = qs.filter(id__in=ids)
    else:
        # Only rows that still contain separators/letters.
        qs = qs.exclude(id_number__regex=r"^\d+$")

    updated = 0
    skipped = 0
    errors: list[dict] = []

    for customer in qs.iterator():
        raw = (customer.id_number or "").strip()
        digits = alegra_client._digits_only(raw)
        if digits == raw:
            skipped += 1
            continue
        if not digits:
            errors.append(
                {
                    "id": str(customer.id),
                    "name": customer.name,
                    "detail": f"Sin dígitos tras formatear ('{raw}'). Corrige el documento.",
                }
            )
            continue
        if Customer.objects.filter(id_type=customer.id_type, id_number=digits).exclude(
            pk=customer.pk
        ).exists():
            errors.append(
                {
                    "id": str(customer.id),
                    "name": customer.name,
                    "detail": (
                        f"Conflicto: '{raw}' → '{digits}' ya existe para "
                        f"{customer.id_type}. Revisa duplicados."
                    ),
                }
            )
            continue
        previous = customer.id_number
        customer.id_number = digits
        try:
            customer.save(update_fields=["id_number", "updated_at"])
        except IntegrityError:
            errors.append(
                {
                    "id": str(customer.id),
                    "name": customer.name,
                    "detail": f"Conflicto al guardar '{digits}' (documento duplicado).",
                }
            )
            continue
        updated += 1
        log_audit_event(
            actor=actor,
            action="CUSTOMER_DOC_NORMALIZED",
            entity="Customer",
            entity_id=str(customer.id),
            metadata={"from": previous, "to": digits},
        )

    return {
        "updated": updated,
        "skipped": skipped,
        "failed": len(errors),
        "errors": errors,
    }

@transaction.atomic
def issue_invoice(invoice_id, *, actor=None) -> Invoice:
    invoice = Invoice.objects.select_for_update(of=("self",)).select_related(
        "sale", "customer"
    ).get(id=invoice_id)

    # Double-emission guards
    if invoice.status == InvoiceStatus.GENERADA or invoice.alegra_id or invoice.number:
        return invoice
    if invoice.status == InvoiceStatus.ENVIANDO:
        raise ValueError(
            "Hay un envío en curso. Usa reconciliar antes de reintentar."
        )

    customer = sync_customer_to_alegra(invoice.customer, actor=actor)
    if not customer.alegra_id:
        invoice.status = InvoiceStatus.FALLIDA
        invoice.last_error = "Cliente sin alegra_id tras sync."
        invoice.save(update_fields=["status", "last_error", "updated_at"])
        return invoice

    invoice.status = InvoiceStatus.ENVIANDO
    invoice.sent_at = timezone.now()
    invoice.attempts += 1
    invoice.save(update_fields=["status", "sent_at", "attempts", "updated_at"])

    try:
        body = alegra_client.create_invoice(invoice, customer_alegra_id=customer.alegra_id)
        invoice.alegra_id = str(body.get("id") or "")
        invoice.number = str(body.get("number") or body.get("numberTemplate", {}).get("number") or "")
        invoice.cufe = str(body.get("cufe") or body.get("stamp", {}).get("cufe") or "")
        invoice.pdf_url = str(body.get("pdf") or body.get("pdfUrl") or "")
        invoice.status = InvoiceStatus.GENERADA
        invoice.confirmed_at = timezone.now()
        invoice.last_error = ""
        invoice.save()
        log_audit_event(
            actor=actor,
            action="INVOICE_ISSUED",
            entity="Invoice",
            entity_id=str(invoice.id),
            metadata={"number": invoice.number, "alegra_id": invoice.alegra_id},
        )
    except Exception as exc:
        invoice.status = InvoiceStatus.FALLIDA
        invoice.last_error = str(exc)[:2000]
        invoice.save(update_fields=["status", "last_error", "updated_at"])
        log_audit_event(
            actor=actor,
            action="INVOICE_FAILED",
            entity="Invoice",
            entity_id=str(invoice.id),
            metadata={"error": str(exc)[:500]},
        )
    return invoice


@transaction.atomic
def reconcile_invoice(invoice_id, *, actor=None) -> Invoice:
    invoice = Invoice.objects.select_for_update(of=("self",)).get(id=invoice_id)
    if invoice.status == InvoiceStatus.GENERADA and invoice.alegra_id:
        return invoice

    found = alegra_client.find_invoice_by_annotation(invoice.idempotency_key)
    if found:
        invoice.alegra_id = str(found.get("id") or invoice.alegra_id)
        invoice.number = str(found.get("number") or invoice.number)
        invoice.cufe = str(found.get("cufe") or invoice.cufe)
        invoice.pdf_url = str(found.get("pdf") or invoice.pdf_url)
        invoice.status = InvoiceStatus.GENERADA
        invoice.confirmed_at = timezone.now()
        invoice.last_error = ""
        invoice.save()
        log_audit_event(
            actor=actor,
            action="INVOICE_RECONCILED",
            entity="Invoice",
            entity_id=str(invoice.id),
            metadata={"alegra_id": invoice.alegra_id},
        )
        return invoice

    # Safe to retry
    if invoice.status in {InvoiceStatus.FALLIDA, InvoiceStatus.ENVIANDO}:
        invoice.status = InvoiceStatus.POR_GENERAR
        invoice.save(update_fields=["status", "updated_at"])
    return invoice


@transaction.atomic
def create_refund(invoice_id, *, reason: str, actor=None) -> Refund:
    invoice = Invoice.objects.select_for_update(of=("self",)).select_related("sale").get(
        id=invoice_id
    )
    sale = invoice.sale

    if invoice.status == InvoiceStatus.POR_GENERAR:
        invoice.status = InvoiceStatus.ANULADA
        invoice.save(update_fields=["status", "updated_at"])
        withdraw_from_consolidated(sale, reason="REFUND", state=SaleState.REFUNDED, actor=actor)
        refund = Refund.objects.create(
            invoice=invoice,
            sale=sale,
            status=RefundStatus.CERRADO,
            reason=reason,
            manual_void_pending=False,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        return refund

    if invoice.status != InvoiceStatus.GENERADA:
        raise ValueError("Solo se reembolsa una factura GENERADA (o se cancela POR_GENERAR).")

    refund = Refund.objects.create(
        invoice=invoice,
        sale=sale,
        status=RefundStatus.SOLICITADO,
        reason=reason,
        manual_void_pending=True,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )

    body = alegra_client.create_credit_note(invoice, reason=reason)
    refund.alegra_credit_note_id = str(body.get("id") or "")
    refund.status = RefundStatus.NOTA_CREDITO_EMITIDA
    refund.save()

    invoice.status = InvoiceStatus.ANULADA
    invoice.save(update_fields=["status", "updated_at"])
    withdraw_from_consolidated(sale, reason="REFUND", state=SaleState.REFUNDED, actor=actor)

    # Reverse inventory if shipped (OneToOne reverse — no shipment_id on sale)
    try:
        shipment = sale.shipment
    except ObjectDoesNotExist:
        shipment = None
    if shipment is not None:
        try:
            from apps.inventory.services import reverse_stock_for_shipment

            reverse_stock_for_shipment(shipment, actor=actor)
        except Exception:
            pass

    log_audit_event(
        actor=actor,
        action="REFUND_CREATED",
        entity="Refund",
        entity_id=str(refund.id),
        metadata={"invoice": str(invoice.id), "credit_note": refund.alegra_credit_note_id},
    )
    return refund


@transaction.atomic
def confirm_void(refund_id, *, actor=None) -> Refund:
    refund = Refund.objects.select_for_update().get(id=refund_id)
    refund.manual_void_pending = False
    refund.status = RefundStatus.CERRADO
    refund.save(update_fields=["manual_void_pending", "status", "updated_at"])
    log_audit_event(
        actor=actor,
        action="REFUND_VOID_CONFIRMED",
        entity="Refund",
        entity_id=str(refund.id),
    )
    return refund
