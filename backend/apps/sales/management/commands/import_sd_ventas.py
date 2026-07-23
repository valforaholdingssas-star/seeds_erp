from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.sales.services.csv_import import commit_csv, xlsx_to_csv_text


class Command(BaseCommand):
    help = "Importa ventas históricas desde un .xlsx (primera hoja) vía commit_csv."

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
        text = xlsx_to_csv_text(data)
        if not text.strip():
            raise CommandError("Hoja vacía o sin encabezados.")

        if options["dry_run"]:
            from apps.sales.services.csv_import import dry_run_csv

            report = dry_run_csv(text)
            self.stdout.write(
                self.style.WARNING(
                    f"dry_run: total={report['total']} valid={report['valid']} "
                    f"invalid={report['invalid']}"
                )
            )
            return

        result = commit_csv(
            text,
            on_duplicate=options["on_duplicate"],
            actor=None,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Importado: created={result['created']} updated={result['updated']} "
                f"skipped={result['skipped']} rejected={result['rejected']}"
            )
        )
