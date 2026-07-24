from django.core.management.base import BaseCommand

from apps.finance.services.seed import seed_finance


class Command(BaseCommand):
    help = "Siembra cuentas EFE, PUC, bancos y reglas de clasificación."

    def handle(self, *args, **options):
        result = seed_finance()
        self.stdout.write(self.style.SUCCESS(f"Finance seed OK: {result}"))
