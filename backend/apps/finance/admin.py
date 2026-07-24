from django.contrib import admin

from apps.finance.models import (
    AccountingAccount,
    Bank,
    BankImportBatch,
    BankMovement,
    ClassificationRule,
    EfeBudget,
    EfeMonthClose,
    FinancialAccount,
)


@admin.register(FinancialAccount)
class FinancialAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "is_leaf", "active", "order")
    list_filter = ("kind", "is_leaf", "active")
    search_fields = ("code", "name", "full_label")


@admin.register(AccountingAccount)
class AccountingAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "attribution", "active")
    search_fields = ("code", "name")


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "importer", "active")
    search_fields = ("name", "account_no")


@admin.register(BankMovement)
class BankMovementAdmin(admin.ModelAdmin):
    list_display = ("date", "bank", "item", "value", "status", "is_interbank", "concept")
    list_filter = ("status", "item", "is_interbank", "bank")
    search_fields = ("concept", "reference", "dedupe_hash")


@admin.register(ClassificationRule)
class ClassificationRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "bank", "concept_contains", "priority", "active", "is_interbank")


@admin.register(BankImportBatch)
class BankImportBatchAdmin(admin.ModelAdmin):
    list_display = ("created_at", "bank", "filename", "rows_created", "rows_duplicated", "dry_run")


admin.site.register(EfeBudget)
admin.site.register(EfeMonthClose)
