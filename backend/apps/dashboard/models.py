from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.common.models import BaseModel


class IndicatorUnit(models.TextChoices):
    COUNT = "COUNT", "Conteo"
    AMOUNT = "AMOUNT", "Monto"
    PERCENT = "PERCENT", "Porcentaje"
    DAYS = "DAYS", "Días"


class IndicatorSeverity(models.TextChoices):
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    CRITICAL = "CRITICAL", "Crítico"


class ControlIndicator(BaseModel):
    key = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=255)
    module = models.CharField(max_length=32, db_index=True)
    description = models.CharField(max_length=512, blank=True)
    unit = models.CharField(
        max_length=16, choices=IndicatorUnit.choices, default=IndicatorUnit.COUNT
    )
    severity = models.CharField(
        max_length=16,
        choices=IndicatorSeverity.choices,
        default=IndicatorSeverity.WARNING,
    )
    warn_threshold = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    crit_threshold = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    target_url = models.CharField(max_length=512, blank=True)
    visible = models.BooleanField(default=True)
    roles = models.JSONField(default=list, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "key"]

    def __str__(self) -> str:
        return self.label


class IndicatorSnapshot(BaseModel):
    indicator = models.ForeignKey(
        ControlIndicator, on_delete=models.CASCADE, related_name="snapshots"
    )
    value = models.DecimalField(max_digits=16, decimal_places=2)
    amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-captured_at"]
        indexes = [
            models.Index(fields=["indicator", "-captured_at"]),
        ]
