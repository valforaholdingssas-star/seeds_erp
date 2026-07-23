from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.geo.models import GeoCatalog
from apps.geo.services import normalize_text

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "divipola_municipios.csv"

# ISO 3166-2:CO (sin prefijo CO-)
DEPT_ISO: dict[str, str] = {
    "Amazonas": "AMA",
    "Antioquia": "ANT",
    "Arauca": "ARA",
    "Archipiélago de San Andrés": "SAP",
    "Atlántico": "ATL",
    "Bogotá D.C.": "DC",
    "Bolívar": "BOL",
    "Boyacá": "BOY",
    "Caldas": "CAL",
    "Caquetá": "CAQ",
    "Casanare": "CAS",
    "Cauca": "CAU",
    "Cesar": "CES",
    "Chocó": "CHO",
    "Córdoba": "COR",
    "Cundinamarca": "CUN",
    "Guainía": "GUA",
    "Guaviare": "GUV",
    "Huila": "HUI",
    "La Guajira": "LAG",
    "Magdalena": "MAG",
    "Meta": "MET",
    "Nariño": "NAR",
    "Norte de Santander": "NSA",
    "Putumayo": "PUT",
    "Quindío": "QUI",
    "Risaralda": "RIS",
    "Santander": "SAN",
    "Sucre": "SUC",
    "Tolima": "TOL",
    "Valle del Cauca": "VAC",
    "Vaupés": "VAU",
    "Vichada": "VID",
}


def dane_city_code(raw: str) -> str:
    """DIVIPOLA municipio (5) → código cabecera Envia/DANE (8) con sufijo 000."""
    digits = "".join(ch for ch in str(raw).strip() if ch.isdigit()).zfill(5)
    if len(digits) >= 8:
        return digits[:8]
    return f"{digits}000"


class Command(BaseCommand):
    help = "Carga el catálogo DIVIPOLA completo (municipios DANE) desde CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--purge-missing",
            action="store_true",
            help="Elimina municipios del catálogo que no están en el CSV.",
        )

    def handle(self, *args, **options):
        if not DATA_PATH.exists():
            self.stderr.write(self.style.ERROR(f"No existe {DATA_PATH}"))
            return

        created = 0
        updated = 0
        skipped = 0
        seen_codes: set[str] = set()
        unknown_depts: set[str] = set()

        with DATA_PATH.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                dept = (row.get("DEPARTAMENTO") or "").strip()
                name = (row.get("MUNICIPIO") or "").strip()
                raw_code = (row.get("CODIGO_MUNICIPIO") or "").strip()
                if not dept or not name or not raw_code:
                    skipped += 1
                    continue
                iso = DEPT_ISO.get(dept)
                if not iso:
                    unknown_depts.add(dept)
                    skipped += 1
                    continue
                code = dane_city_code(raw_code)
                seen_codes.add(code)
                # Bogotá: nombre canónico corto para matching de pedidos
                display = "Bogotá" if code.startswith("11001") else name
                obj, was_created = GeoCatalog.objects.update_or_create(
                    municipality_code=code,
                    defaults={
                        "municipality": display,
                        "department": dept,
                        "department_iso": iso,
                        "search": normalize_text(display),
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        deleted = 0
        if options["purge_missing"] and seen_codes:
            qs = GeoCatalog.objects.exclude(municipality_code__in=seen_codes)
            deleted = qs.count()
            qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"GeoCatalog: {created} creados, {updated} actualizados"
                + (f", {deleted} eliminados" if deleted else "")
                + (f", {skipped} omitidos" if skipped else "")
                + f". Total CSV: {len(seen_codes)}."
            )
        )
        if unknown_depts:
            self.stderr.write(
                self.style.WARNING(f"Departamentos sin ISO: {sorted(unknown_depts)}")
            )
