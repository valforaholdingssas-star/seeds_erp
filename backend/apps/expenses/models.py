from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint

from apps.common.models import BaseModel
from apps.finance.models import AccountingAttribution


class AttachmentKind(models.TextChoices):
    PAYMENT_PROOF = "PAYMENT_PROOF", "Comprobante de pago"
    PROVIDER_INVOICE = "PROVIDER_INVOICE", "Factura del proveedor"
    OTHER = "OTHER", "Otro"


class ExpenseStatus(BaseModel):
    key = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=128)
    order = models.IntegerField(default=0)
    feeds_efe = models.BooleanField(default=False)
    color = models.CharField(max_length=32, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "key"]

    def __str__(self) -> str:
        return self.label


class Expense(BaseModel):
    title = models.CharField(max_length=512)
    concept = models.CharField(max_length=512, blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    bank_account = models.ForeignKey(
        "finance.Bank",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expenses",
    )
    expense_date = models.DateField(db_index=True)
    payment_date = models.DateField(null=True, blank=True)
    efe_account = models.ForeignKey(
        "finance.FinancialAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expenses",
    )
    accounting_account = models.ForeignKey(
        "finance.AccountingAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expenses",
    )
    attribution = models.CharField(
        max_length=24,
        choices=AccountingAttribution.choices,
        blank=True,
    )
    status = models.ForeignKey(
        ExpenseStatus,
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responsible_expenses",
    )
    checked = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_expenses",
    )
    iva_discountable = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    iva_already_discounted = models.BooleanField(default=False)
    amortize = models.BooleanField(default=False)
    amortization_months = models.PositiveIntegerField(null=True, blank=True)
    bank_movement = models.ForeignKey(
        "finance.BankMovement",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expense_links",
    )
    reconciled = models.BooleanField(default=False)
    alegra_synced = models.BooleanField(default=False)
    alegra_id = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_expenses",
    )

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        indexes = [
            models.Index(fields=["status", "expense_date"]),
            models.Index(fields=["reconciled", "expense_date"]),
            models.Index(fields=["iva_already_discounted"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.amount})"

    @property
    def effective_concept(self) -> str:
        return (self.concept or self.title or "").strip()


def expense_attachment_upload_to(instance: "ExpenseAttachment", filename: str) -> str:
    return f"expenses/{instance.expense_id}/{instance.kind}/{filename}"


class ExpenseAttachment(BaseModel):
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="attachments"
    )
    kind = models.CharField(max_length=32, choices=AttachmentKind.choices)
    file = models.FileField(upload_to=expense_attachment_upload_to)
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=128, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expense_attachments",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.kind}: {self.filename}"


class ExpenseAmortizationEntry(BaseModel):
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="amortization_entries"
    )
    period_month = models.PositiveSmallIntegerField()
    period_year = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    efe_account = models.ForeignKey(
        "finance.FinancialAccount",
        on_delete=models.PROTECT,
        related_name="amortization_entries",
    )

    class Meta:
        ordering = ["period_year", "period_month"]
        constraints = [
            UniqueConstraint(
                fields=["expense", "period_month", "period_year"],
                name="uq_amort_period",
            )
        ]
        indexes = [
            models.Index(fields=["period_year", "period_month", "efe_account"]),
        ]

    def __str__(self) -> str:
        return f"{self.expense_id} {self.period_year}-{self.period_month:02d} {self.amount}"
