from django.core.management.base import BaseCommand

from apps.sellers.services import ensure_system_vendors


class Command(BaseCommand):
    help = "Crea vendedores de sistema (ECOMMERCE, FERIAS) y opcionales observados."

    def handle(self, *args, **options):
        created = ensure_system_vendors()
        extras = [
            ("VENDEDORA 1", ["Marina", "Maji"]),
            ("RETENCIÓN 1", ["Lau", "Dani"]),
        ]
        from apps.sellers.models import Vendedor

        extra_created = 0
        for name, aliases in extras:
            _, was_created = Vendedor.objects.get_or_create(
                name=name,
                defaults={"is_system": False, "active": True, "aliases": aliases},
            )
            if was_created:
                extra_created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Vendedores: {len(created)} sistema, {extra_created} comerciales."
            )
        )
