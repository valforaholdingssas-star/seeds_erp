from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.logistics.models import Shipment
from apps.sales.services.normalization import recalculate_shipping


class Command(BaseCommand):
    help = (
        "Recalcula IVA/neto de ventas usando el costo Envia de la guía "
        "(no el flete cobrado al cliente)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo reporta cuántas ventas se actualizarían.",
        )

    def handle(self, *args, **options):
        qs = (
            Shipment.objects.select_related("sale")
            .filter(shipping_cost__isnull=False)
            .exclude(shipping_cost=0)
        )
        updated = 0
        for shipment in qs.iterator(chunk_size=200):
            sale = shipment.sale
            if not sale:
                continue
            if options["dry_run"]:
                updated += 1
                continue
            recalculate_shipping(sale, Decimal(shipment.shipping_cost))
            updated += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"{'dry_run: ' if options['dry_run'] else ''}recalc={updated}"
            )
        )
