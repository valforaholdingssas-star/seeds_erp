from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class ShipmentStatus(models.TextChoices):
    POR_GENERAR = "POR_GENERAR", "Por generar guía"
    GUIA_FALLIDA = "GUIA_FALLIDA", "Guía fallida"
    LISTO_PARA_ENVIAR = "LISTO_PARA_ENVIAR", "Listo para enviar"
    ENVIADO = "ENVIADO", "Enviado"
    REVISAR = "REVISAR", "Revisar / no enviar"
    CANCELADA = "CANCELADA", "Cancelada"


class BatchJobType(models.TextChoices):
    GENERATE_SHIPMENTS = "GENERATE_SHIPMENTS", "Generar guías"
    FORMAT_ADDRESSES = "FORMAT_ADDRESSES", "Formatear direcciones"
    MARK_SENT = "MARK_SENT", "Marcar enviados"
    ISSUE_INVOICES = "ISSUE_INVOICES", "Emitir facturas"
    WOO_RESYNC = "WOO_RESYNC", "Resync WooCommerce"


class BatchJobStatus(models.TextChoices):
    PENDING = "PENDING", "Pendiente"
    RUNNING = "RUNNING", "En curso"
    COMPLETED = "COMPLETED", "Completado"
    CANCELLED = "CANCELLED", "Cancelado"


class BatchItemStatus(models.TextChoices):
    PENDING = "PENDING", "Pendiente"
    RUNNING = "RUNNING", "En curso"
    SUCCESS = "SUCCESS", "Éxito"
    FAILED = "FAILED", "Fallido"
    SKIPPED = "SKIPPED", "Omitido"


class BatchJob(BaseModel):
    job_type = models.CharField(max_length=32, choices=BatchJobType.choices)
    status = models.CharField(
        max_length=16, choices=BatchJobStatus.choices, default=BatchJobStatus.PENDING
    )
    total = models.PositiveIntegerField(default=0)
    done = models.PositiveIntegerField(default=0)
    success = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="batch_jobs",
    )
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]


class BatchJobItem(BaseModel):
    batch = models.ForeignKey(BatchJob, on_delete=models.CASCADE, related_name="items")
    ref_type = models.CharField(max_length=64, blank=True)
    ref_id = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=16, choices=BatchItemStatus.choices, default=BatchItemStatus.PENDING
    )
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]


class Shipment(BaseModel):
    sale = models.OneToOneField(
        "sales.ConsolidatedSale",
        on_delete=models.CASCADE,
        related_name="shipment",
    )
    # editable mirrors
    address_mirror = models.CharField(max_length=512, blank=True)
    city_mirror = models.CharField(max_length=128, blank=True)
    state_mirror = models.CharField(max_length=128, blank=True)
    # geo normalization
    geo_city = models.ForeignKey(
        "geo.GeoCatalog",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shipments",
    )
    geo_state_code = models.CharField(max_length=8, blank=True)
    address_formatted = models.CharField(max_length=512, blank=True)
    do_not_ship = models.BooleanField(default=False)
    # Envia
    status = models.CharField(
        max_length=24,
        choices=ShipmentStatus.choices,
        default=ShipmentStatus.POR_GENERAR,
        db_index=True,
    )
    carrier = models.CharField(max_length=64, default="coordinadora")
    service = models.CharField(max_length=64, default="ground")
    tracking_number = models.CharField(max_length=128, blank=True, db_index=True)
    tracking_url = models.URLField(blank=True, max_length=512)
    label_url = models.URLField(blank=True)
    shipping_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    generated_city = models.CharField(max_length=128, blank=True)
    generated_state = models.CharField(max_length=128, blank=True)
    generated_address = models.CharField(max_length=512, blank=True)
    warning = models.BooleanField(default=False)
    warning_detail = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    envia_shipment_id = models.CharField(max_length=128, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "warning"]),
            models.Index(fields=["do_not_ship", "status"]),
        ]

    def __str__(self) -> str:
        return f"Shipment {self.sale.external_id} [{self.status}]"
