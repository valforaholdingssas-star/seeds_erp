from django.core.management.base import BaseCommand

from apps.sales.services.payment_methods import (
    backfill_payment_methods_from_accounts,
    ensure_default_payment_methods,
)


class Command(BaseCommand):
    help = "Siembra medios de pago por defecto y backfill desde payment_account."

    def handle(self, *args, **options):
        created = ensure_default_payment_methods()
        result = backfill_payment_methods_from_accounts()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed: {len(created)} nuevos · total={result['methods']} · "
                f"filas enlazadas={result['linked_rows']}"
            )
        )
