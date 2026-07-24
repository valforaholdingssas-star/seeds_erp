from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class FinancialAccountKind(models.TextChoices):
    VENTAS = "VENTAS", "Ventas"
    COGS = "COGS", "COGS"
    INGRESO = "INGRESO", "Ingreso/Recaudo"
    COSTO = "COSTO", "Costo operativo"
    GASTO = "GASTO", "Gasto"
    PASIVO = "PASIVO", "Otros pasivos"
    AJUSTE = "AJUSTE", "Ajuste"
    ADMIN = "ADMIN", "Gasto administrativo"


class FinancialSign(models.TextChoices):
    IN = "IN", "Entra"
    OUT = "OUT", "Sale"


class FinancialAccount(BaseModel):
    """Cuenta EFE (modelo financiero jerárquico)."""

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    full_label = models.CharField(max_length=255, blank=True, db_index=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    kind = models.CharField(
        max_length=16,
        choices=FinancialAccountKind.choices,
        default=FinancialAccountKind.GASTO,
    )
    is_leaf = models.BooleanField(default=True)
    sign = models.CharField(max_length=8, choices=FinancialSign.choices, blank=True)
    active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "code"]

    def __str__(self) -> str:
        return self.full_label or f"{self.code} {self.name}"

    def save(self, *args, **kwargs):
        if not self.full_label:
            self.full_label = f"{self.code}. {self.name}"
        super().save(*args, **kwargs)


class AccountingAttribution(models.TextChoices):
    ADMINISTRATIVO = "ADMINISTRATIVO", "Administrativo"
    VENTAS = "VENTAS", "Ventas"
    OPERACIONAL = "OPERACIONAL", "Operacional"
    COMPARTIDO = "COMPARTIDO", "Compartido"
    NIAT = "NIAT", "NIAT"


class AccountingAccount(BaseModel):
    """Cuenta Contable (PUC)."""

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    attribution = models.CharField(
        max_length=24,
        choices=AccountingAttribution.choices,
        default=AccountingAttribution.COMPARTIDO,
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class BankKind(models.TextChoices):
    BANK = "BANK", "Banco"
    GATEWAY = "GATEWAY", "Pasarela"
    CASH = "CASH", "Efectivo"


class Bank(BaseModel):
    name = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=16, choices=BankKind.choices, default=BankKind.BANK)
    account_no = models.CharField(max_length=64, blank=True)
    importer = models.CharField(
        max_length=32,
        blank=True,
        help_text="Parser CSV: bancolombia|mercadopago|bold|nequi",
    )
    active = models.BooleanField(default=True)
    report_aliases = models.JSONField(
        default=list,
        blank=True,
        help_text="Nombres de payment_account/medios que mapean a este banco en auditoría.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class MovementItem(models.TextChoices):
    INGRESO = "INGRESO", "Ingreso"
    EGRESO = "EGRESO", "Egreso"


class MovementStatus(models.TextChoices):
    POR_CLASIFICAR = "POR_CLASIFICAR", "Por clasificar"
    CLASIFICADO = "CLASIFICADO", "Clasificado"
    CONCILIADO = "CONCILIADO", "Conciliado"


class BankImportBatch(BaseModel):
    bank = models.ForeignKey(Bank, on_delete=models.PROTECT, related_name="import_batches")
    filename = models.CharField(max_length=255, blank=True)
    rows_total = models.PositiveIntegerField(default=0)
    rows_created = models.PositiveIntegerField(default=0)
    rows_duplicated = models.PositiveIntegerField(default=0)
    rows_errors = models.PositiveIntegerField(default=0)
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    dry_run = models.BooleanField(default=False)
    errors = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_import_batches",
    )

    class Meta:
        ordering = ["-created_at"]


class BankMovement(BaseModel):
    bank = models.ForeignKey(Bank, on_delete=models.PROTECT, related_name="movements")
    date = models.DateField(db_index=True)
    value = models.DecimalField(max_digits=16, decimal_places=2)
    item = models.CharField(max_length=16, choices=MovementItem.choices)
    concept = models.CharField(max_length=512, blank=True)
    reference = models.CharField(max_length=128, blank=True)
    comment = models.CharField(max_length=512, blank=True)
    financial_account = models.ForeignKey(
        FinancialAccount,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movements",
    )
    accounting_account = models.ForeignKey(
        AccountingAccount,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movements",
    )
    attribution = models.CharField(max_length=24, blank=True)
    is_interbank = models.BooleanField(default=False)
    total_tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    retefuente = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    reteica = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    reteiva = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    status = models.CharField(
        max_length=24,
        choices=MovementStatus.choices,
        default=MovementStatus.POR_CLASIFICAR,
        db_index=True,
    )
    alegra_synced = models.BooleanField(default=False)
    alegra_id = models.CharField(max_length=64, blank=True)
    import_batch = models.ForeignKey(
        BankImportBatch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movements",
    )
    dedupe_hash = models.CharField(max_length=64, db_index=True)
    tx_code = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["bank", "dedupe_hash"],
                name="uq_bankmov_bank_dedupe",
            )
        ]
        indexes = [
            models.Index(fields=["status", "date"]),
            models.Index(fields=["bank", "date"]),
            models.Index(fields=["is_interbank", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.bank.name} {self.date} {self.value}"


class ClassificationRule(BaseModel):
    name = models.CharField(max_length=128)
    bank = models.ForeignKey(
        Bank,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="classification_rules",
        help_text="Vacío = aplica a todos los bancos",
    )
    concept_contains = models.CharField(max_length=255)
    financial_account = models.ForeignKey(
        FinancialAccount,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rules",
    )
    accounting_account = models.ForeignKey(
        AccountingAccount,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rules",
    )
    attribution = models.CharField(max_length=24, blank=True)
    is_interbank = models.BooleanField(default=False)
    priority = models.IntegerField(default=100)
    active = models.BooleanField(default=True)
    auto_apply = models.BooleanField(
        default=True,
        help_text="Si true, asigna al importar; si false solo sugiere.",
    )

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self) -> str:
        return self.name


class EfeBudget(BaseModel):
    financial_account = models.ForeignKey(
        FinancialAccount, on_delete=models.CASCADE, related_name="budgets"
    )
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()  # 1-12
    amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["financial_account", "year", "month"],
                name="uq_efe_budget_account_ym",
            )
        ]
        ordering = ["year", "month", "financial_account__code"]


class EfeMonthClose(BaseModel):
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    closed_at = models.DateTimeField(auto_now_add=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="efe_closes",
    )
    note = models.CharField(max_length=512, blank=True)
    unclassified_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0")
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["year", "month"], name="uq_efe_month_close")
        ]
        ordering = ["-year", "-month"]
