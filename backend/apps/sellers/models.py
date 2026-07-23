from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Vendedor(BaseModel):
    """
    Entidad comercial parametrizable.
    Puede tener User asociado o no (ECOMMERCE / FERIAS no son personas).
    """

    name = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vendedores",
    )
    is_system = models.BooleanField(
        default=False,
        help_text="True para ECOMMERCE/FERIAS (no personas).",
    )
    active = models.BooleanField(default=True, db_index=True)
    aliases = models.JSONField(
        default=list,
        blank=True,
        help_text='Alias de texto crudo, p.ej. ["Marina","Maji","Lau"].',
    )
    needs_review = models.BooleanField(
        default=False,
        help_text="Creado automáticamente desde un commercial_raw desconocido.",
    )
    monthly_goal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        help_text="Meta mensual del vendedor (COP). Null → usa business.sales_goal_month.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Vendedor"
        verbose_name_plural = "Vendedores"
        indexes = [
            models.Index(fields=["active", "is_system"]),
            models.Index(fields=["needs_review", "active"]),
        ]

    def __str__(self) -> str:
        return self.name
