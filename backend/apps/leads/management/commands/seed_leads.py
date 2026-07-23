from django.core.management.base import BaseCommand

from apps.leads.models import Lead, LeadStatus


SEED = [
    {"name": "María Gómez", "email": "maria@example.com", "city": "Bogotá", "source": "web", "status": LeadStatus.NUEVO},
    {"name": "Juan Torres", "phone": "3001112233", "city": "Medellín", "source": "feria", "status": LeadStatus.CONTACTADO},
    {"name": "Laura Díaz", "email": "laura@example.com", "city": "Cali", "source": "referido", "status": LeadStatus.CALIFICADO},
    {"name": "Pedro Ruiz", "city": "Barranquilla", "source": "kommo", "status": LeadStatus.DESCARTADO, "notes": "Sin presupuesto"},
]


class Command(BaseCommand):
    help = "Crea leads de demo si la tabla está vacía."

    def handle(self, *args, **options):
        if Lead.objects.exists():
            self.stdout.write("Leads ya existen; skip seed.")
            return
        for row in SEED:
            Lead.objects.create(**row)
        self.stdout.write(self.style.SUCCESS(f"{len(SEED)} leads creados."))
