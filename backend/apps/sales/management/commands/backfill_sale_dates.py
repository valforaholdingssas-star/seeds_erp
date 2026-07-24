"""
Re-sync closed_at from channel sources (Kommo FECHA DE CIERRE / Woo date_created).

Usage:
  python manage.py backfill_sale_dates --dry-run
  python manage.py backfill_sale_dates --source KOMMO
  python manage.py backfill_sale_dates --limit 50
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.sales.models import ConsolidatedSale, EcommerceSale, KommoSale, SaleSource
from apps.sales.services.kommo import _parse_kommo_closed_at, _cf_any
from apps.sales.services.kommo_client import enrich_from_webhook_payload, fetch_lead, kommo_configured
from apps.sales.services.woocommerce import _parse_closed_at


class Command(BaseCommand):
    help = "Backfill ConsolidatedSale.closed_at from channel dates (not ERP ingest)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            choices=["KOMMO", "ECOMMERCE", "ALL"],
            default="ALL",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        source = options["source"]
        dry = options["dry_run"]
        limit = options["limit"]
        updated = 0
        skipped = 0
        errors = 0

        if source in {"KOMMO", "ALL"}:
            qs = KommoSale.objects.all().order_by("-created_at")
            if limit:
                qs = qs[:limit]
            for sale in qs:
                try:
                    new_dt = self._kommo_closed(sale)
                    if not new_dt:
                        skipped += 1
                        continue
                    if sale.closed_at and abs((sale.closed_at - new_dt).total_seconds()) < 60:
                        skipped += 1
                        continue
                    self.stdout.write(
                        f"KOMMO {sale.external_id}: {sale.closed_at} → {new_dt}"
                    )
                    if not dry:
                        with transaction.atomic():
                            sale.closed_at = new_dt
                            sale.save(update_fields=["closed_at", "updated_at"])
                            ConsolidatedSale.objects.filter(
                                source=SaleSource.KOMMO,
                                external_id=sale.external_id,
                            ).update(closed_at=new_dt)
                    updated += 1
                except Exception as exc:
                    errors += 1
                    self.stderr.write(f"KOMMO {sale.external_id}: {exc}")

        if source in {"ECOMMERCE", "ALL"}:
            qs = EcommerceSale.objects.all().order_by("-created_at")
            if limit:
                qs = qs[:limit]
            for sale in qs:
                try:
                    # Prefer payload date if present on related raw event
                    new_dt = None
                    if sale.raw_event and isinstance(sale.raw_event.payload, dict):
                        body = sale.raw_event.payload
                        if isinstance(body.get("body"), dict):
                            body = body["body"]
                        new_dt = _parse_closed_at(body.get("date_created"))
                    if not new_dt:
                        skipped += 1
                        continue
                    if sale.closed_at and abs((sale.closed_at - new_dt).total_seconds()) < 60:
                        skipped += 1
                        continue
                    self.stdout.write(
                        f"ECOMMERCE {sale.external_id}: {sale.closed_at} → {new_dt}"
                    )
                    if not dry:
                        with transaction.atomic():
                            sale.closed_at = new_dt
                            sale.save(update_fields=["closed_at", "updated_at"])
                            ConsolidatedSale.objects.filter(
                                source=SaleSource.ECOMMERCE,
                                external_id=sale.external_id,
                            ).update(closed_at=new_dt)
                    updated += 1
                except Exception as exc:
                    errors += 1
                    self.stderr.write(f"ECOMMERCE {sale.external_id}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"{'DRY ' if dry else ''}updated={updated} skipped={skipped} errors={errors}"
            )
        )

    def _kommo_closed(self, sale: KommoSale):
        # Try custom fields already stored in extra / re-fetch lead
        if kommo_configured():
            lead = fetch_lead(sale.external_id)
            cfs = lead.get("custom_fields_values") or []
            raw = _cf_any(
                cfs,
                "FECHA DE CIERRE",
                "Fecha de cierre",
                "Fecha de Cierre",
                "fecha de cierre",
            )
            return _parse_kommo_closed_at(raw)
        if sale.raw_event and isinstance(sale.raw_event.payload, dict):
            lead, _ = enrich_from_webhook_payload(sale.raw_event.payload)
            cfs = lead.get("custom_fields_values") or []
            raw = _cf_any(
                cfs,
                "FECHA DE CIERRE",
                "Fecha de cierre",
                "Fecha de Cierre",
                "fecha de cierre",
            )
            return _parse_kommo_closed_at(raw)
        return None
