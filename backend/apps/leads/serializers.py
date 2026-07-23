from rest_framework import serializers

from apps.leads.models import Lead, LeadStatus
from apps.sellers.models import Vendedor


class LeadSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source="seller.name", read_only=True, default=None)
    converted_sale_external_id = serializers.CharField(
        source="converted_sale.external_id",
        read_only=True,
        default=None,
    )

    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "city",
            "source",
            "status",
            "seller",
            "seller_name",
            "notes",
            "converted_sale",
            "converted_sale_external_id",
            "extra",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "seller_name",
            "converted_sale_external_id",
        ]

    def validate_name(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value

    def validate_status(self, value: str) -> str:
        if value not in LeadStatus.values:
            raise serializers.ValidationError("Estado de lead inválido.")
        return value

    def validate_seller(self, value: Vendedor | None) -> Vendedor | None:
        if value and not value.active:
            raise serializers.ValidationError("El vendedor está inactivo.")
        return value

    def validate(self, attrs):
        status = attrs.get("status", getattr(self.instance, "status", LeadStatus.NUEVO))
        converted_sale = attrs.get(
            "converted_sale",
            getattr(self.instance, "converted_sale", None),
        )
        if status == LeadStatus.CONVERTIDO and converted_sale is None and "converted_sale" in attrs:
            # Allow CONVERTIDO without sale (link later); no hard fail.
            pass
        if converted_sale is not None and status != LeadStatus.CONVERTIDO:
            attrs["status"] = LeadStatus.CONVERTIDO
        return attrs
