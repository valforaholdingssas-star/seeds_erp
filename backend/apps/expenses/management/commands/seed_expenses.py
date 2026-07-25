from django.core.management.base import BaseCommand

from apps.expenses.services.seed import seed_expense_statuses


class Command(BaseCommand):
    help = "Seed expense pipeline statuses"

    def handle(self, *args, **options):
        result = seed_expense_statuses()
        self.stdout.write(self.style.SUCCESS(f"Expense statuses: {result}"))
