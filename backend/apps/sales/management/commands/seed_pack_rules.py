from django.core.management.base import BaseCommand

from apps.sales.models import ProductPackRule


class Command(BaseCommand):
    help = "Seed de reglas de pack (WooCommerce product 602 → ×3)."

    def handle(self, *args, **options):
        obj, created = ProductPackRule.objects.update_or_create(
            woo_product_id="602",
            defaults={
                "name_contains": "3 kits",
                "multiplier": 3,
                "active": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"ProductPackRule 602 ×3 {'creada' if created else 'actualizada'}."
            )
        )
