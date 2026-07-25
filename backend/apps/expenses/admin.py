from django.contrib import admin

from apps.expenses.models import (
    Expense,
    ExpenseAmortizationEntry,
    ExpenseAttachment,
    ExpenseStatus,
)


@admin.register(ExpenseStatus)
class ExpenseStatusAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "order", "feeds_efe", "active")
    list_filter = ("feeds_efe", "active")


class AttachmentInline(admin.TabularInline):
    model = ExpenseAttachment
    extra = 0
    readonly_fields = ("created_at",)


class AmortInline(admin.TabularInline):
    model = ExpenseAmortizationEntry
    extra = 0
    readonly_fields = ("period_year", "period_month", "amount", "efe_account")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "amount",
        "expense_date",
        "status",
        "efe_account",
        "reconciled",
    )
    list_filter = ("status", "reconciled", "amortize")
    search_fields = ("title", "concept")
    inlines = [AttachmentInline, AmortInline]
