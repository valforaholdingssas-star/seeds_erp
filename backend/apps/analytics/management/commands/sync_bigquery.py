from django.core.management.base import BaseCommand

from apps.analytics.services.bigquery_export import sync_analytics_to_bigquery


class Command(BaseCommand):
    help = "Sync sales/items/shipments to BigQuery (Looker Studio)."

    def handle(self, *args, **options):
        result = sync_analytics_to_bigquery()
        if result.get("skipped"):
            self.stdout.write(self.style.WARNING(result.get("message") or "Skipped"))
            return
        if result.get("ok"):
            self.stdout.write(self.style.SUCCESS(str(result)))
        else:
            self.stderr.write(self.style.ERROR(str(result)))
