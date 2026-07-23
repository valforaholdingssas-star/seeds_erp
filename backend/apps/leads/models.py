from django.db import models

from apps.common.models import BaseModel


class LeadStatus(models.TextChoices):
    NUEVO = "NUEVO", "Nuevo"
    CONTACTADO = "CONTACTADO", "Contactado"
    CALIFICADO = "CALIFICADO", "Calificado"
    CONVERTIDO = "CONVERTIDO", "Convertido"
    DESCARTADO = "DESCARTADO", "Descartado"


class Lead(BaseModel):
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=64, blank=True, default="")
    city = models.CharField(max_length=128, blank=True, default="")
    source = models.CharField(
        max_length=64,
        blank=True,
        default="manual",
        help_text="web, feria, referido, kommo, manual…",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=LeadStatus.choices,
        default=LeadStatus.NUEVO,
        db_index=True,
    )
    seller = models.ForeignKey(
        "sellers.Vendedor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    notes = models.TextField(blank=True, default="")
    converted_sale = models.ForeignKey(
        "sales.ConsolidatedSale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_leads",
    )
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "source"]),
            models.Index(fields=["seller", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.status})"
