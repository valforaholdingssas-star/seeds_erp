from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class ProductColor(models.TextChoices):
    DORADO = "DORADO", "Dorado"
    PLATEADO = "PLATEADO", "Plateado"
    OTRO = "OTRO", "Otro"


class Product(BaseModel):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=16, choices=ProductColor.choices, blank=True)
    tipo = models.CharField(max_length=128, blank=True)
    woo_product_id = models.CharField(max_length=64, blank=True, db_index=True)
    active = models.BooleanField(default=True)
    stock = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=0)
    is_generic = models.BooleanField(
        default=False,
        help_text="Producto genérico dorado/plateado para ítems sin mapeo.",
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["color", "tipo"]),
            models.Index(fields=["active", "stock"]),
        ]

    def __str__(self) -> str:
        return f"{self.sku} · {self.name}"


class Material(BaseModel):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    unit = models.CharField(max_length=32, default="u")
    stock = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    reorder_level = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.sku} · {self.name}"


class KardexItemType(models.TextChoices):
    PRODUCT = "PRODUCT", "Producto"
    MATERIAL = "MATERIAL", "Material"


class KardexMovement(models.TextChoices):
    IN = "IN", "Entrada"
    OUT = "OUT", "Salida"
    ADJUST = "ADJUST", "Ajuste"


class KardexReason(models.TextChoices):
    DISPATCH = "DISPATCH", "Despacho"
    PURCHASE = "PURCHASE", "Compra"
    MANUAL_ADJUST = "MANUAL_ADJUST", "Ajuste manual"
    PRODUCTION = "PRODUCTION", "Producción"
    REFUND = "REFUND", "Reembolso"


class KardexEntry(BaseModel):
    item_type = models.CharField(max_length=16, choices=KardexItemType.choices)
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.PROTECT, related_name="kardex"
    )
    material = models.ForeignKey(
        Material, null=True, blank=True, on_delete=models.PROTECT, related_name="kardex"
    )
    movement = models.CharField(max_length=16, choices=KardexMovement.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    balance = models.DecimalField(max_digits=14, decimal_places=3)
    reason = models.CharField(max_length=32, choices=KardexReason.choices)
    ref_type = models.CharField(max_length=64, blank=True)
    ref_id = models.CharField(max_length=64, blank=True, db_index=True)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="kardex_entries",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item_type", "reason"]),
            models.Index(fields=["ref_type", "ref_id"]),
            models.Index(fields=["product", "created_at"]),
        ]
