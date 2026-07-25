from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.sales.services.csv_import import commit_xlsx, dry_run_xlsx


class Command(BaseCommand):
    help = "Importa ventas históricas desde un .xlsx (primera hoja)."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Ruta al archivo .xlsx")
        parser.add_argument(
            "--on-duplicate",
            choices=("skip", "update"),
            default="skip",
            help="Comportamiento ante external_id duplicado (default: skip).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo valida sin escribir en BD.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"No existe: {path}")
        if path.suffix.lower() not in {".xlsx", ".xlsm"}:
            raise CommandError("Se espera un archivo .xlsx")

        data = path.read_bytes()
        if options["dry_run"]:
            report = dry_run_xlsx(data)
            if report["total"] == 0:
                raise CommandError("Hoja vacía o sin encabezados.")
            self.stdout.write(
                self.style.WARNING(
                    f"dry_run: total={report['total']} valid={report['valid']} "
                    f"invalid={report['invalid']}"
                )
            )
            return

        result = commit_xlsx(
            data,
            on_duplicate=options["on_duplicate"],
            actor=None,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Importado: created={result['created']} updated={result['updated']} "
                f"skipped={result['skipped']} rejected={result['rejected']}"
            )
        )
