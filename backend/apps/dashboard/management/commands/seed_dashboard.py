from django.core.management.base import BaseCommand

from apps.dashboard.services.seed import seed_dashboard


class Command(BaseCommand):
    help = "Seed control dashboard indicators"

    def handle(self, *args, **options):
        result = seed_dashboard()
        self.stdout.write(self.style.SUCCESS(f"Dashboard indicators: {result}"))
