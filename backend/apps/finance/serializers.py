from rest_framework import serializers

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


class FinancialAccountSerializer(serializers.ModelSerializer):
    parent_code = serializers.CharField(source="parent.code", read_only=True)

    class Meta:
        model = FinancialAccount
        fields = [
            "id",
            "code",
            "name",
            "full_label",
            "parent",
            "parent_code",
            "kind",
            "is_leaf",
            "sign",
            "active",
            "order",
            "created_at",
            "updated_at",
        ]


class AccountingAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingAccount
        fields = [
            "id",
            "code",
            "name",
            "attribution",
            "active",
            "created_at",
            "updated_at",
        ]


class BankSerializer(serializers.ModelSerializer):
    last_import = serializers.SerializerMethodField()
    coverage = serializers.SerializerMethodField()

    class Meta:
        model = Bank
        fields = [
            "id",
            "name",
            "kind",
            "account_no",
            "importer",
            "active",
            "report_aliases",
            "last_import",
            "coverage",
            "created_at",
            "updated_at",
        ]

    def get_last_import(self, obj) -> dict | None:
        cache = self.context.get("last_imports") or {}
        return cache.get(str(obj.id))

    def get_coverage(self, obj) -> dict | None:
        cache = self.context.get("coverages") or {}
        return cache.get(str(obj.id))


class BankImportBatchSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source="bank.name", read_only=True)

    class Meta:
        model = BankImportBatch
        fields = [
            "id",
            "bank",
            "bank_name",
            "filename",
            "rows_total",
            "rows_created",
            "rows_duplicated",
            "rows_errors",
            "date_from",
            "date_to",
            "dry_run",
            "errors",
            "created_at",
        ]


class ClassificationRuleSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source="bank.name", read_only=True)
    efe_label = serializers.CharField(source="financial_account.full_label", read_only=True)
    puc_label = serializers.SerializerMethodField()

    class Meta:
        model = ClassificationRule
        fields = [
            "id",
            "name",
            "bank",
            "bank_name",
            "concept_contains",
            "financial_account",
            "efe_label",
            "accounting_account",
            "puc_label",
            "attribution",
            "is_interbank",
            "priority",
            "active",
            "auto_apply",
            "created_at",
            "updated_at",
        ]

    def get_puc_label(self, obj) -> str:
        if not obj.accounting_account_id:
            return ""
        a = obj.accounting_account
        return f"{a.code} {a.name}"


class BankMovementSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source="bank.name", read_only=True)
    efe_code = serializers.CharField(source="financial_account.code", read_only=True)
    efe_label = serializers.CharField(source="financial_account.full_label", read_only=True)
    puc_code = serializers.CharField(source="accounting_account.code", read_only=True)

    class Meta:
        model = BankMovement
        fields = [
            "id",
            "bank",
            "bank_name",
            "date",
            "value",
            "item",
            "concept",
            "reference",
            "comment",
            "financial_account",
            "efe_code",
            "efe_label",
            "accounting_account",
            "puc_code",
            "attribution",
            "is_interbank",
            "total_tax",
            "retefuente",
            "reteica",
            "reteiva",
            "status",
            "alegra_synced",
            "alegra_id",
            "import_batch",
            "dedupe_hash",
            "tx_code",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "dedupe_hash",
            "import_batch",
            "created_at",
            "updated_at",
        ]


class BulkClassifySerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    financial_account = serializers.UUIDField(required=False, allow_null=True)
    accounting_account = serializers.UUIDField(required=False, allow_null=True)
    attribution = serializers.CharField(required=False, allow_blank=True, default="")
    is_interbank = serializers.BooleanField(required=False)
    status = serializers.CharField(required=False, allow_blank=True)


class EfeBudgetSerializer(serializers.ModelSerializer):
    efe_code = serializers.CharField(source="financial_account.code", read_only=True)

    class Meta:
        model = EfeBudget
        fields = [
            "id",
            "financial_account",
            "efe_code",
            "year",
            "month",
            "amount",
        ]


class EfeMonthCloseSerializer(serializers.ModelSerializer):
    class Meta:
        model = EfeMonthClose
        fields = [
            "id",
            "year",
            "month",
            "closed_at",
            "note",
            "unclassified_pct",
        ]
        read_only_fields = ["id", "closed_at", "unclassified_pct"]
