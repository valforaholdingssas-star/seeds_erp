from django.core.management.base import BaseCommand

from apps.inventory.models import Product, ProductColor
from apps.sales.kit_types import KitType


class Command(BaseCommand):
    help = "Seed productos por tipo de kit (10/20/30) × color + genéricos."

    def handle(self, *args, **options):
        seeds: list[tuple] = [
            ("GEN-DORADO", "Seeds Dorados (genérico)", ProductColor.DORADO, "", True, 100),
            ("GEN-PLATEADO", "Seeds Plateados (genérico)", ProductColor.PLATEADO, "", True, 100),
        ]
        for kit in KitType:
            for color, color_label in (
                (ProductColor.DORADO, "Dorado"),
                (ProductColor.PLATEADO, "Plateado"),
            ):
                sku = f"{kit.value}-{color}"
                name = f"{kit.label} · {color_label}"
                seeds.append((sku, name, color, kit.value, False, 50))

        created = 0
        updated = 0
        for sku, name, color, tipo, generic, stock in seeds:
            obj, was = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "color": color,
                    "tipo": tipo,
                    "is_generic": generic,
                    "active": True,
                    "stock": stock,
                    "reorder_level": 10,
                },
            )
            if was:
                created += 1
            elif obj.tipo != tipo or obj.name != name:
                obj.tipo = tipo
                obj.name = name
                obj.save(update_fields=["tipo", "name", "updated_at"])
                updated += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Productos kit: {created} creados, {updated} actualizados "
                f"(tipos {', '.join(KitType.values)})."
            )
        )
