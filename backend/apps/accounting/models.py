from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint

from apps.common.models import BaseModel


class InvoiceStatus(models.TextChoices):
    POR_GENERAR = "POR_GENERAR", "Por generar"
    ENVIANDO = "ENVIANDO", "Enviando"
    GENERADA = "GENERADA", "Generada"
    FALLIDA = "FALLIDA", "Fallida"
    ANULADA = "ANULADA", "Anulada"


class RefundStatus(models.TextChoices):
    SOLICITADO = "SOLICITADO", "Solicitado"
    NOTA_CREDITO_EMITIDA = "NOTA_CREDITO_EMITIDA", "Nota crédito emitida"
    CERRADO = "CERRADO", "Cerrado"


class Customer(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="customers",
    )
    name = models.CharField(max_length=255)
    id_type = models.CharField(max_length=16, default="CC")
    id_number = models.CharField(max_length=64, db_index=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    address = models.CharField(max_length=512, blank=True)
    city = models.CharField(max_length=128, blank=True)
    alegra_id = models.CharField(max_length=64, blank=True, db_index=True)
    alegra_synced = models.BooleanField(default=False)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["id_type", "id_number"], name="uq_customer_doc"),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.id_type} {self.id_number})"


class Invoice(BaseModel):
    sale = models.OneToOneField(
        "sales.ConsolidatedSale",
        on_delete=models.CASCADE,
        related_name="invoice",
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="invoices"
    )
    status = models.CharField(
        max_length=16,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.POR_GENERAR,
        db_index=True,
    )
    alegra_id = models.CharField(max_length=64, blank=True, db_index=True)
    number = models.CharField(max_length=64, blank=True)
    cufe = models.CharField(max_length=128, blank=True)
    pdf_url = models.URLField(blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    iva = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    last_error = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(max_length=128, unique=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Invoice {self.idempotency_key} [{self.status}]"


class Refund(BaseModel):
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name="refunds"
    )
    sale = models.ForeignKey(
        "sales.ConsolidatedSale",
        on_delete=models.PROTECT,
        related_name="refunds",
    )
    status = models.CharField(
        max_length=32,
        choices=RefundStatus.choices,
        default=RefundStatus.SOLICITADO,
        db_index=True,
    )
    reason = models.TextField()
    alegra_credit_note_id = models.CharField(max_length=64, blank=True)
    manual_void_pending = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="refunds_created",
    )

    class Meta:
        ordering = ["-created_at"]
