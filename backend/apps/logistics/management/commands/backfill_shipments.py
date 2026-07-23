from django.core.management.base import BaseCommand

from apps.logistics.services.shipments import ensure_shipment_for_sale
from apps.sales.models import ConsolidatedSale, SaleState


class Command(BaseCommand):
    help = "Crea Shipment faltantes para ventas ACTIVE con requires_shipping."

    def handle(self, *args, **options):
        qs = ConsolidatedSale.objects.filter(
            state=SaleState.ACTIVE, requires_shipping=True, shipment__isnull=True
        )
        created = 0
        for sale in qs:
            if ensure_shipment_for_sale(sale):
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Shipments creados: {created}"))
