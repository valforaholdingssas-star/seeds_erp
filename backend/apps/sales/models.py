from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, UniqueConstraint

from apps.common.models import BaseModel


class SaleSource(models.TextChoices):
    ECOMMERCE = "ECOMMERCE", "Ecommerce"
    SHOPIFY = "SHOPIFY", "Ecommerce 2"
    KOMMO = "KOMMO", "Kommo"
    FERIAS = "FERIAS", "Ferias"
    MANUAL = "MANUAL", "Manual"


class SaleState(models.TextChoices):
    DRAFT = "DRAFT", "Borrador"
    ACTIVE = "ACTIVE", "Activa"
    WITHDRAWN = "WITHDRAWN", "Retirada"
    REFUNDED = "REFUNDED", "Reembolsada"


class SaleColor(models.TextChoices):
    DORADO = "DORADO", "Dorado"
    PLATEADO = "PLATEADO", "Plateado"


class FulfillmentType(models.TextChoices):
    """Cómo se entrega el pedido. Solo ENVIA entra a generación de guías."""

    ENVIA = "ENVIA", "Envia (guía)"
    DOMICILIO = "DOMICILIO", "Domicilio fuera de Envia"
    OFICINA = "OFICINA", "Visita / recoger en oficina"


def fulfillment_requires_envia(fulfillment_type: str) -> bool:
    return fulfillment_type == FulfillmentType.ENVIA


class PaymentMethod(BaseModel):
    """
    Medio de pago parametrizable (a dónde pagó el cliente).
    Renombrar propaga a ventas vía FK + payment_account denormalizado.
    """

    name = models.CharField(max_length=128, unique=True, db_index=True)
    active = models.BooleanField(default=True, db_index=True)
    aliases = models.JSONField(
        default=list,
        blank=True,
        help_text='Alias de texto crudo, p.ej. ["nequi","Nequi Colombia"].',
    )
    is_system = models.BooleanField(
        default=False,
        help_text="Semilla del sistema (Nequi, Efectivo…). Se puede desactivar, no borrar.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Medio de pago"
        verbose_name_plural = "Medios de pago"

    def __str__(self) -> str:
        return self.name


VALID_CONSOLIDATION_STATUSES = frozenset({"processing", "completed"})
WITHDRAW_STATUSES = frozenset({"cancelled", "failed", "refunded", "error"})

# Pedidos ecommerce que no llegaron a consolidado y requieren seguimiento comercial.
FAILED_ECOMMERCE_STATUSES = frozenset(
    {
        "pending",
        "failed",
        "cancelled",
        "on-hold",
        "checkout-draft",
        "error",
    }
)


class FollowUpStatus(models.TextChoices):
    POR_CONTACTAR = "POR_CONTACTAR", "Por contactar"
    CONTACTADO = "CONTACTADO", "Contactado"
    EN_SEGUIMIENTO = "EN_SEGUIMIENTO", "En seguimiento"
    CERRADO = "CERRADO", "Cerrado"


class SourceSaleBase(BaseModel):
    external_id = models.CharField(max_length=64, db_index=True)
    raw_event = models.ForeignKey(
        "integrations.RawWebhookEvent",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_sales",
    )
    deal_name = models.CharField(max_length=255, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    amount_shipping = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    payment_account = models.CharField(max_length=128, blank=True)
    payment_method = models.ForeignKey(
        PaymentMethod,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_sales",
    )
    income_source = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=64, db_index=True, default="processing")
    stage = models.CharField(max_length=128, blank=True)
    commercial_raw = models.CharField(max_length=128, blank=True)
    customer_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    id_number = models.CharField(max_length=64, blank=True)
    address_raw = models.CharField(max_length=512, blank=True)
    city_raw = models.CharField(max_length=128, blank=True)
    state_raw = models.CharField(max_length=128, blank=True)
    qty_dorados = models.PositiveIntegerField(default=0)
    qty_plateados = models.PositiveIntegerField(default=0)
    tipo_dorados = models.CharField(max_length=128, blank=True)
    tipo_plateados = models.CharField(max_length=128, blank=True)
    symptoms = models.CharField(max_length=255, blank=True)
    order_notes = models.TextField(blank=True)
    age = models.CharField(max_length=32, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    consolidated_sale = models.ForeignKey(
        "sales.ConsolidatedSale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_sources",
    )
    requires_shipping = models.BooleanField(
        default=True,
        help_text="Derivado de fulfillment_type: True solo si ENVIA.",
    )
    fulfillment_type = models.CharField(
        max_length=16,
        choices=FulfillmentType.choices,
        default=FulfillmentType.ENVIA,
        db_index=True,
        help_text="ENVIA → guías Envia. DOMICILIO/OFICINA → no generan guía.",
    )
    follow_up_status = models.CharField(
        max_length=24,
        choices=FollowUpStatus.choices,
        default=FollowUpStatus.POR_CONTACTAR,
        db_index=True,
        help_text="Seguimiento comercial de pedidos no consolidados (fallidos/pendientes).",
    )
    contacted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    contacted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_contacts",
    )
    follow_up_notes = models.TextField(blank=True)

    class Meta:
        abstract = True


class EcommerceSale(SourceSaleBase):
    class Meta:
        constraints = [
            UniqueConstraint(fields=["external_id"], name="uq_ecommerce_external_id"),
        ]
        indexes = [models.Index(fields=["status", "closed_at"])]


class ShopifySale(SourceSaleBase):
    """Canal Shopify en paralelo a WooCommerce (EcommerceSale)."""

    class Meta:
        constraints = [
            UniqueConstraint(fields=["external_id"], name="uq_shopify_external_id"),
        ]
        indexes = [models.Index(fields=["status", "closed_at"])]


class KommoSale(SourceSaleBase):
    class Meta:
        constraints = [
            UniqueConstraint(fields=["external_id"], name="uq_kommo_external_id"),
        ]
        indexes = [models.Index(fields=["status", "closed_at"])]


class FeriaSale(SourceSaleBase):
    class Meta:
        constraints = [
            UniqueConstraint(fields=["external_id"], name="uq_feria_external_id"),
        ]


class ManualSale(SourceSaleBase):
    class Meta:
        constraints = [
            UniqueConstraint(fields=["external_id"], name="uq_manual_external_id"),
        ]


class ConsolidatedSale(BaseModel):
    source = models.CharField(max_length=16, choices=SaleSource.choices, db_index=True)
    external_id = models.CharField(max_length=64, db_index=True)
    seller = models.ForeignKey(
        "sellers.Vendedor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales",
    )
    customer_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    id_number = models.CharField(max_length=64, blank=True, db_index=True)
    address_raw = models.CharField(max_length=512, blank=True)
    city_raw = models.CharField(max_length=128, blank=True, db_index=True)
    state_raw = models.CharField(max_length=128, blank=True)
    amount_products = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    amount_shipping = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    iva_generated = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    net_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    payment_account = models.CharField(max_length=128, blank=True)
    payment_method = models.ForeignKey(
        PaymentMethod,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales",
    )
    income_source = models.CharField(max_length=32, blank=True, db_index=True)
    status = models.CharField(max_length=64, db_index=True, default="processing")
    state = models.CharField(
        max_length=16,
        choices=SaleState.choices,
        default=SaleState.ACTIVE,
        db_index=True,
    )
    deal_name = models.CharField(max_length=255, blank=True)
    stage = models.CharField(max_length=128, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    symptoms = models.CharField(max_length=255, blank=True)
    order_notes = models.TextField(blank=True)
    age = models.CharField(max_length=32, blank=True)
    requires_shipping = models.BooleanField(
        default=True,
        help_text="Derivado de fulfillment_type: True solo si ENVIA.",
    )
    fulfillment_type = models.CharField(
        max_length=16,
        choices=FulfillmentType.choices,
        default=FulfillmentType.ENVIA,
        db_index=True,
        help_text="ENVIA → guías Envia. DOMICILIO/OFICINA → no generan guía.",
    )
    withdrawn_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["source", "external_id"], name="uq_sale_source_extid"),
        ]
        indexes = [
            models.Index(fields=["state", "closed_at"]),
            models.Index(fields=["source", "state"]),
            models.Index(fields=["seller", "state"]),
            models.Index(fields=["city_raw", "state"]),
        ]
        ordering = ["-closed_at", "-created_at"]

    def __str__(self) -> str:
        return f"{self.source}:{self.external_id}"


class SaleItem(BaseModel):
    sale = models.ForeignKey(
        ConsolidatedSale, on_delete=models.CASCADE, related_name="items"
    )
    color = models.CharField(max_length=16, choices=SaleColor.choices)
    tipo = models.CharField(max_length=128, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    woo_product_id = models.CharField(max_length=64, blank=True)
    product_name = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [models.Index(fields=["color", "tipo"])]


class ProductPackRule(BaseModel):
    """Multiplicadores de packs WooCommerce (parametrizable)."""

    woo_product_id = models.CharField(max_length=64, blank=True, db_index=True)
    name_contains = models.CharField(max_length=128, blank=True)
    multiplier = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["woo_product_id"],
                condition=~Q(woo_product_id=""),
                name="uq_pack_woo_product_id",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.woo_product_id or self.name_contains} ×{self.multiplier}"
