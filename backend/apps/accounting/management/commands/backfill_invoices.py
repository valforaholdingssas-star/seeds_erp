from django.core.management.base import BaseCommand

from apps.accounting.services.invoicing import ensure_invoice_for_sale
from apps.sales.models import ConsolidatedSale, SaleState


class Command(BaseCommand):
    help = "Crea facturas POR_GENERAR faltantes para ventas ACTIVE."

    def handle(self, *args, **options):
        qs = ConsolidatedSale.objects.filter(state=SaleState.ACTIVE, invoice__isnull=True)
        n = 0
        for sale in qs:
            ensure_invoice_for_sale(sale)
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Facturas encoladas: {n}"))
