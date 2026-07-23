from django.apps import AppConfig


class AccountingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounting"
    label = "accounting"
    verbose_name = "Contabilidad"

    def ready(self) -> None:
        from apps.accounting import signals  # noqa: F401
