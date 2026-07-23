from __future__ import annotations

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from apps.geo.models import GeoCatalog
from apps.geo.services import normalize_text

# Seed mínimo de municipios frecuentes (DANE). Ampliar con CSV oficial después.
SEED_MUNICIPALITIES = [
    ("Bogotá", "11001000", "Bogotá D.C.", "DC", -74.0721, 4.7110),
    ("Medellín", "05001000", "Antioquia", "ANT", -75.5636, 6.2476),
    ("Cali", "76001000", "Valle del Cauca", "VAC", -76.5225, 3.4516),
    ("Barranquilla", "08001000", "Atlántico", "ATL", -74.7813, 10.9685),
    ("Cartagena", "13001000", "Bolívar", "BOL", -75.5144, 10.3910),
    ("Bucaramanga", "68001000", "Santander", "SAN", -73.1198, 7.1193),
    ("Pereira", "66001000", "Risaralda", "RIS", -75.6961, 4.8133),
    ("Manizales", "17001000", "Caldas", "CAL", -75.5138, 5.0703),
    ("Santa Marta", "47001000", "Magdalena", "MAG", -74.1990, 11.2408),
    ("Cúcuta", "54001000", "Norte de Santander", "NSA", -72.5078, 7.8891),
    ("Ibagué", "73001000", "Tolima", "TOL", -75.2322, 4.4389),
    ("Villavicencio", "50001000", "Meta", "MET", -73.6266, 4.1420),
    ("Pasto", "52001000", "Nariño", "NAR", -77.2811, 1.2136),
    ("Montería", "23001000", "Córdoba", "COR", -75.8814, 8.74798),
    ("Neiva", "41001000", "Huila", "HUI", -75.2819, 2.9273),
    ("Armenia", "63001000", "Quindío", "QUI", -75.6811, 4.5339),
    ("Popayán", "19001000", "Cauca", "CAU", -76.6147, 2.4448),
    ("Valledupar", "20001000", "Cesar", "CES", -73.2591, 10.4631),
    ("Sincelejo", "70001000", "Sucre", "SUC", -75.3978, 9.3047),
    ("Tunja", "15001000", "Boyacá", "BOY", -73.3678, 5.5353),
    ("Envigado", "05266000", "Antioquia", "ANT", -75.5800, 6.1699),
    ("Itagüí", "05360000", "Antioquia", "ANT", -75.5991, 6.1846),
    ("Soacha", "25754000", "Cundinamarca", "CUN", -74.2144, 4.5794),
    ("Chía", "25175000", "Cundinamarca", "CUN", -74.0586, 4.8616),
    ("Zipaquirá", "25899000", "Cundinamarca", "CUN", -74.0058, 5.0221),
]


class Command(BaseCommand):
    help = "Carga el catálogo geográfico mínimo (municipios DANE frecuentes)."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for name, code, dept, iso, lng, lat in SEED_MUNICIPALITIES:
            obj, was_created = GeoCatalog.objects.update_or_create(
                municipality_code=code,
                defaults={
                    "municipality": name,
                    "department": dept,
                    "department_iso": iso,
                    "search": normalize_text(name),
                    "point": Point(lng, lat, srid=4326),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(
            self.style.SUCCESS(f"GeoCatalog: {created} creados, {updated} actualizados.")
        )
