from rest_framework import serializers

from apps.expenses.models import (
    Expense,
    ExpenseAmortizationEntry,
    ExpenseAttachment,
    ExpenseStatus,
)
from apps.expenses.services.amortization import regenerate_amortization
from apps.expenses.services.transitions import TransitionError, transition_expense


class ExpenseStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseStatus
        fields = [
            "id",
            "key",
            "label",
            "order",
            "feeds_efe",
            "color",
            "active",
            "created_at",
            "updated_at",
        ]


class ExpenseAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseAttachment
        fields = [
            "id",
            "expense",
            "kind",
            "filename",
            "mime_type",
            "uploaded_by",
            "created_at",
        ]
        read_only_fields = fields


class ExpenseAmortizationEntrySerializer(serializers.ModelSerializer):
    efe_label = serializers.CharField(source="efe_account.full_label", read_only=True)

    class Meta:
        model = ExpenseAmortizationEntry
        fields = [
            "id",
            "period_year",
            "period_month",
            "amount",
            "efe_account",
            "efe_label",
        ]


class ExpenseSerializer(serializers.ModelSerializer):
    status_key = serializers.CharField(source="status.key", read_only=True)
    status_label = serializers.CharField(source="status.label", read_only=True)
    status_color = serializers.CharField(source="status.color", read_only=True)
    feeds_efe = serializers.BooleanField(source="status.feeds_efe", read_only=True)
    bank_name = serializers.CharField(source="bank_account.name", read_only=True, default="")
    efe_label = serializers.CharField(source="efe_account.full_label", read_only=True, default="")
    responsible_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    attachments = ExpenseAttachmentSerializer(many=True, read_only=True)
    amortization_entries = ExpenseAmortizationEntrySerializer(many=True, read_only=True)
    has_payment_proof = serializers.SerializerMethodField()
    has_provider_invoice = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = [
            "id",
            "title",
            "concept",
            "amount",
            "bank_account",
            "bank_name",
            "expense_date",
            "payment_date",
            "efe_account",
            "efe_label",
            "accounting_account",
            "attribution",
            "status",
            "status_key",
            "status_label",
            "status_color",
            "feeds_efe",
            "responsible",
            "responsible_name",
            "checked",
            "approved_by",
            "iva_discountable",
            "iva_already_discounted",
            "amortize",
            "amortization_months",
            "bank_movement",
            "reconciled",
            "alegra_synced",
            "alegra_id",
            "created_by",
            "created_by_name",
            "attachments",
            "amortization_entries",
            "has_payment_proof",
            "has_provider_invoice",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_by",
            "approved_by",
            "alegra_synced",
            "alegra_id",
            "reconciled",
        ]

    def get_responsible_name(self, obj):
        if not obj.responsible_id:
            return ""
        return obj.responsible.get_full_name() or obj.responsible.username

    def get_created_by_name(self, obj):
        if not obj.created_by_id:
            return ""
        return obj.created_by.get_full_name() or obj.created_by.username

    def get_has_payment_proof(self, obj):
        return any(a.kind == "PAYMENT_PROOF" for a in obj.attachments.all())

    def get_has_provider_invoice(self, obj):
        return any(a.kind == "PROVIDER_INVOICE" for a in obj.attachments.all())

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        if not validated_data.get("concept"):
            validated_data["concept"] = validated_data.get("title", "")
        expense = super().create(validated_data)
        if expense.status.feeds_efe:
            regenerate_amortization(expense, allow_closed=False)
        return expense

    def update(self, instance, validated_data):
        new_status = validated_data.pop("status", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if not instance.concept:
            instance.concept = instance.title
        instance.save()

        if new_status and new_status.pk != instance.status_id:
            request = self.context.get("request")
            actor = request.user if request else None
            try:
                instance, _ = transition_expense(
                    instance, status=new_status, actor=actor
                )
            except TransitionError as exc:
                raise serializers.ValidationError({"status": str(exc)}) from exc
        elif instance.status.feeds_efe:
            # amount / amortize / date / efe changes
            try:
                regenerate_amortization(instance, allow_closed=False)
            except ValueError as exc:
                raise serializers.ValidationError({"detail": str(exc)}) from exc
        return instance


class TransitionSerializer(serializers.Serializer):
    status = serializers.PrimaryKeyRelatedField(queryset=ExpenseStatus.objects.filter(active=True))
    allow_closed = serializers.BooleanField(default=False, required=False)


class BulkUpdateSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    efe_account = serializers.UUIDField(required=False, allow_null=True)
    status = serializers.UUIDField(required=False, allow_null=True)
    attribution = serializers.CharField(required=False, allow_blank=True)
    checked = serializers.BooleanField(required=False)
    iva_already_discounted = serializers.BooleanField(required=False)


class ReconcileSerializer(serializers.Serializer):
    bank_movement = serializers.UUIDField()


class CreatePayableSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["reembolso", "cuenta"])
    title = serializers.CharField(max_length=512)
    amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    expense_date = serializers.DateField()
    concept = serializers.CharField(required=False, allow_blank=True, default="")
    bank_account = serializers.UUIDField(required=False, allow_null=True)
    efe_account = serializers.UUIDField(required=False, allow_null=True)
    responsible = serializers.UUIDField(required=False, allow_null=True)


class MarkPaidSerializer(serializers.Serializer):
    payment_date = serializers.DateField()
    bank_account = serializers.UUIDField(required=False, allow_null=True)
    efe_account = serializers.UUIDField(required=False, allow_null=True)
    register_in_efe = serializers.BooleanField(required=False, default=False)
