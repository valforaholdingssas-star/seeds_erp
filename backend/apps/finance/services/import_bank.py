from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.audit.services import log_audit_event
from apps.finance.importers.parsers import PARSERS, ParsedRow, assign_dedupe_hashes
from apps.finance.models import Bank, BankImportBatch, BankMovement, MovementStatus
from apps.finance.services.classify import apply_rules_to_movement


def import_bank_csv(
    *,
    bank: Bank,
    text: str,
    filename: str = "",
    dry_run: bool = True,
    actor=None,
) -> dict:
    importer = (bank.importer or "").strip().lower()
    parser = PARSERS.get(importer)
    if not parser:
        raise ValueError(
            f"Banco {bank.name} no tiene importador configurado (importer={bank.importer!r})."
        )

    parsed = parser(text)
    hashed = assign_dedupe_hashes(parsed)
    errors = [r.error for r, _ in hashed if r.error]
    valid: list[tuple[ParsedRow, str]] = [(r, h) for r, h in hashed if not r.error and h]

    existing = set(
        BankMovement.objects.filter(
            bank=bank, dedupe_hash__in=[h for _, h in valid]
        ).values_list("dedupe_hash", flat=True)
    )
    to_create = [(r, h) for r, h in valid if h not in existing]
    duplicated = len(valid) - len(to_create)

    preview = [
        {
            "date": r.date.isoformat(),
            "value": str(r.value),
            "item": r.item,
            "concept": r.concept[:120],
            "reference": r.reference,
            "dedupe_hash": h,
            "duplicate": h in existing,
        }
        for r, h in valid[:200]
    ]

    batch = None
    created_ids: list[str] = []
    if not dry_run:
        with transaction.atomic():
            batch = BankImportBatch.objects.create(
                bank=bank,
                filename=filename[:255],
                rows_total=len(parsed),
                rows_created=0,
                rows_duplicated=duplicated,
                rows_errors=len(errors),
                dry_run=False,
                errors=errors[:100],
                created_by=actor if getattr(actor, "is_authenticated", False) else None,
            )
            objs = []
            for row, h in to_create:
                mov = BankMovement(
                    bank=bank,
                    date=row.date,
                    value=row.value,
                    item=row.item,
                    concept=row.concept[:512],
                    reference=row.reference[:128],
                    comment=row.comment[:512],
                    tx_code=row.tx_code[:32],
                    dedupe_hash=h,
                    import_batch=batch,
                    status=MovementStatus.POR_CLASIFICAR,
                )
                apply_rules_to_movement(mov, save=False)
                objs.append(mov)
            BankMovement.objects.bulk_create(objs, ignore_conflicts=True)
            batch.rows_created = BankMovement.objects.filter(import_batch=batch).count()
            batch.save(update_fields=["rows_created", "updated_at"])
            created_ids = [str(x.id) for x in BankMovement.objects.filter(import_batch=batch)]
            log_audit_event(
                actor=actor,
                action="BANK_IMPORT_COMMIT",
                entity="BankImportBatch",
                entity_id=str(batch.id),
                metadata={
                    "bank": bank.name,
                    "created": batch.rows_created,
                    "duplicated": duplicated,
                    "errors": len(errors),
                },
            )
    else:
        batch = BankImportBatch.objects.create(
            bank=bank,
            filename=filename[:255],
            rows_total=len(parsed),
            rows_created=0,
            rows_duplicated=duplicated,
            rows_errors=len(errors),
            dry_run=True,
            errors=errors[:100],
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )

    return {
        "batch_id": str(batch.id) if batch else None,
        "dry_run": dry_run,
        "bank": bank.name,
        "rows_total": len(parsed),
        "rows_valid": len(valid),
        "rows_new": len(to_create),
        "rows_duplicated": duplicated,
        "rows_errors": len(errors),
        "errors": errors[:50],
        "preview": preview,
        "created_ids": created_ids[:50],
    }
