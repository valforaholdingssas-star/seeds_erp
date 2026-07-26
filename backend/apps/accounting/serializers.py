from rest_framework import serializers

from apps.accounting.models import Customer, Invoice, InvoiceStatus, Refund


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "id_type",
            "id_number",
            "email",
            "phone",
            "address",
            "city",
            "alegra_id",
            "alegra_synced",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "alegra_id", "alegra_synced", "created_at", "updated_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    sale_external_id = serializers.CharField(source="sale.external_id", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_id_number = serializers.CharField(source="customer.id_number", read_only=True)
    customer_alegra_synced = serializers.BooleanField(
        source="customer.alegra_synced", read_only=True
    )
    customer_alegra_id = serializers.CharField(source="customer.alegra_id", read_only=True)
    can_issue = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "sale",
            "sale_external_id",
            "customer",
            "customer_name",
            "customer_id_number",
            "customer_alegra_synced",
            "customer_alegra_id",
            "can_issue",
            "status",
            "alegra_id",
            "number",
            "cufe",
            "pdf_url",
            "total",
            "iva",
            "last_error",
            "attempts",
            "idempotency_key",
            "sent_at",
            "confirmed_at",
            "created_at",
            "updated_at",
        ]

    def get_can_issue(self, obj) -> bool:
        if obj.status not in {InvoiceStatus.POR_GENERAR, InvoiceStatus.FALLIDA}:
            return False
        customer = obj.customer
        return bool(customer and customer.alegra_id and customer.alegra_synced)


class RefundSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)
    sale_external_id = serializers.CharField(source="sale.external_id", read_only=True)

    class Meta:
        model = Refund
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "sale",
            "sale_external_id",
            "status",
            "reason",
            "alegra_credit_note_id",
            "manual_void_pending",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class RefundCreateSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField()
    reason = serializers.CharField(min_length=3)


class IdsSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)


class OptionalIdsSerializer(serializers.Serializer):
    """Empty/omitted ids = process all matching records (caller decides scope)."""

    ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True, default=list
    )
