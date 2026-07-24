from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from apps.sales.models import ConsolidatedSale, SaleItem
from apps.sellers.models import Vendedor
from apps.sales.models import PaymentMethod


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = [
            "id",
            "color",
            "tipo",
            "quantity",
            "woo_product_id",
            "product_name",
        ]


class SellerMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendedor
        fields = ["id", "name", "is_system"]


class PaymentMethodMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ["id", "name", "active"]


class ConsolidatedSaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    seller_detail = SellerMiniSerializer(source="seller", read_only=True)
    payment_method_detail = PaymentMethodMiniSerializer(source="payment_method", read_only=True)
    shipment = serializers.SerializerMethodField()
    invoice = serializers.SerializerMethodField()

    class Meta:
        model = ConsolidatedSale
        fields = [
            "id",
            "source",
            "external_id",
            "seller",
            "seller_detail",
            "customer_name",
            "email",
            "phone",
            "id_number",
            "address_raw",
            "city_raw",
            "state_raw",
            "amount_products",
            "amount_shipping",
            "total_value",
            "iva_generated",
            "net_value",
            "payment_account",
            "payment_method",
            "payment_method_detail",
            "income_source",
            "status",
            "state",
            "deal_name",
            "stage",
            "closed_at",
            "symptoms",
            "order_notes",
            "age",
            "requires_shipping",
            "fulfillment_type",
            "withdrawn_reason",
            "items",
            "shipment",
            "invoice",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "iva_generated",
            "net_value",
            "amount_products",
            "created_at",
            "updated_at",
            "items",
            "seller_detail",
            "payment_method_detail",
            "shipment",
            "invoice",
        ]

    def get_shipment(self, obj):
        try:
            s = obj.shipment
        except ObjectDoesNotExist:
            return None
        return {
            "id": str(s.id),
            "status": s.status,
            "tracking_number": s.tracking_number,
            "tracking_url": s.tracking_url,
            "label_url": s.label_url,
            "shipping_cost": str(s.shipping_cost) if s.shipping_cost is not None else None,
            "warning": s.warning,
            "do_not_ship": s.do_not_ship,
            "city_mirror": s.city_mirror,
            "address_mirror": s.address_mirror,
        }

    def get_invoice(self, obj):
        try:
            inv = obj.invoice
        except ObjectDoesNotExist:
            return None
        return {
            "id": str(inv.id),
            "status": inv.status,
            "number": inv.number,
            "total": str(inv.total),
            "iva": str(inv.iva),
            "pdf_url": inv.pdf_url,
        }


class ConsolidatedSaleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsolidatedSale
        fields = [
            "customer_name",
            "email",
            "phone",
            "id_number",
            "address_raw",
            "city_raw",
            "state_raw",
            "payment_account",
            "payment_method",
            "symptoms",
            "order_notes",
            "requires_shipping",
            "fulfillment_type",
            "seller",
        ]

    def update(self, instance, validated_data):
        from apps.sales.services.payment_methods import resolve_payment_method
        from apps.sales.services.fulfillment import apply_fulfillment, sync_shipment_for_fulfillment

        pm = validated_data.get("payment_method")
        if pm is None and "payment_account" in validated_data:
            pm = resolve_payment_method(validated_data.get("payment_account") or "")
            if pm:
                validated_data["payment_method"] = pm
                validated_data["payment_account"] = pm.name
        elif pm is not None:
            validated_data["payment_account"] = pm.name

        merged = {
            "fulfillment_type": validated_data.get(
                "fulfillment_type", instance.fulfillment_type
            ),
            "requires_shipping": validated_data.get(
                "requires_shipping", instance.requires_shipping
            ),
        }
        apply_fulfillment(merged)
        validated_data["fulfillment_type"] = merged["fulfillment_type"]
        validated_data["requires_shipping"] = merged["requires_shipping"]

        sale = super().update(instance, validated_data)
        sync_shipment_for_fulfillment(sale, actor=self.context.get("request") and self.context["request"].user)
        return sale


class BulkUpdateSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    fields = serializers.DictField()


class InternalSaleCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=255)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    id_number = serializers.CharField(required=False, allow_blank=True)
    address_raw = serializers.CharField(required=False, allow_blank=True)
    city_raw = serializers.CharField(required=False, allow_blank=True)
    state_raw = serializers.CharField(required=False, allow_blank=True)
    total_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    amount_shipping = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=Decimal("0")
    )
    payment_account = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.UUIDField(required=False, allow_null=True)
    qty_dorados = serializers.IntegerField(required=False, default=0, min_value=0)
    qty_plateados = serializers.IntegerField(required=False, default=0, min_value=0)
    tipo_dorados = serializers.CharField(required=False, allow_blank=True)
    tipo_plateados = serializers.CharField(required=False, allow_blank=True)
    symptoms = serializers.CharField(required=False, allow_blank=True)
    order_notes = serializers.CharField(required=False, allow_blank=True)
    age = serializers.CharField(required=False, allow_blank=True)
    requires_shipping = serializers.BooleanField(required=False, default=True)
    fulfillment_type = serializers.ChoiceField(
        choices=["ENVIA", "DOMICILIO", "OFICINA"],
        required=False,
        default="ENVIA",
    )
    commercial_raw = serializers.CharField(required=False, allow_blank=True)
    deal_name = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        from apps.sales.kit_types import normalize_kit_type
        from apps.sales.services.fulfillment import apply_fulfillment

        apply_fulfillment(attrs)
        if attrs.get("tipo_dorados"):
            attrs["tipo_dorados"] = normalize_kit_type(attrs["tipo_dorados"])
        if attrs.get("tipo_plateados"):
            attrs["tipo_plateados"] = normalize_kit_type(attrs["tipo_plateados"])
        if attrs.get("requires_shipping"):
            if not attrs.get("address_raw") or not attrs.get("city_raw"):
                raise serializers.ValidationError(
                    "Dirección y ciudad son obligatorias para envío con Envia."
                )
        if not attrs.get("qty_dorados") and not attrs.get("qty_plateados"):
            raise serializers.ValidationError(
                "Indica al menos la cantidad de kits dorados o plateados."
            )
        # Si hay cantidad de un color, exigir tipo de kit
        if attrs.get("qty_dorados") and not attrs.get("tipo_dorados"):
            raise serializers.ValidationError(
                {"tipo_dorados": "Elige el tipo de kit (10, 20 o 30 semillas)."}
            )
        if attrs.get("qty_plateados") and not attrs.get("tipo_plateados"):
            raise serializers.ValidationError(
                {"tipo_plateados": "Elige el tipo de kit (10, 20 o 30 semillas)."}
            )
        return attrs


class ManualSaleCreateSerializer(InternalSaleCreateSerializer):
    commercial_raw = serializers.CharField(required=True)

    def validate_commercial_raw(self, value):
        if not value.strip():
            raise serializers.ValidationError("El vendedor es obligatorio.")
        return value


class WithdrawSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
