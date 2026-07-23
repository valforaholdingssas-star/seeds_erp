from django.core.management.base import BaseCommand

from apps.ai.models import Document, DocumentKind
from apps.ai.services import ingest_document


SEED = [
    {
        "kind": DocumentKind.POLICY,
        "title": "Política de envíos",
        "content": (
            "Seeds despacha a nivel nacional con Envia. "
            "Las guías se generan una a una. El operador confirma el despacho en bodega."
        ),
    },
    {
        "kind": DocumentKind.POLICY,
        "title": "Política de facturación",
        "content": (
            "Las facturas se emiten en Alegra. Un reembolso genera nota crédito y "
            "requiere anulación manual pendiente de confirmación."
        ),
    },
    {
        "kind": DocumentKind.PRODUCT,
        "title": "Pack Seeds ×3",
        "content": (
            "El producto 602 se vende en pack de 3 unidades. "
            "El inventario descuenta materiales dorados y plateados al marcar enviado."
        ),
    },
]


class Command(BaseCommand):
    help = "Ingesta documentos de conocimiento demo."

    def handle(self, *args, **options):
        created = 0
        for row in SEED:
            if Document.objects.filter(kind=row["kind"], title=row["title"]).exists():
                continue
            ingest_document(**row)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"{created} documentos AI ingeridos."))
