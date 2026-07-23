from decimal import Decimal

from rest_framework import serializers

from apps.inventory.models import KardexEntry, Material, Product


class ProductSerializer(serializers.ModelSerializer):
    low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "sku",
            "name",
            "color",
            "tipo",
            "woo_product_id",
            "active",
            "stock",
            "reorder_level",
            "is_generic",
            "low_stock",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "stock", "created_at", "updated_at", "low_stock"]

    def get_low_stock(self, obj) -> bool:
        return obj.stock <= obj.reorder_level


class MaterialSerializer(serializers.ModelSerializer):
    low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = [
            "id",
            "sku",
            "name",
            "unit",
            "stock",
            "reorder_level",
            "active",
            "low_stock",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "stock", "created_at", "updated_at", "low_stock"]

    def get_low_stock(self, obj) -> bool:
        return obj.stock <= obj.reorder_level


class KardexEntrySerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source="product.sku", read_only=True, default="")
    product_name = serializers.CharField(source="product.name", read_only=True, default="")
    material_sku = serializers.CharField(source="material.sku", read_only=True, default="")
    material_name = serializers.CharField(source="material.name", read_only=True, default="")

    class Meta:
        model = KardexEntry
        fields = [
            "id",
            "item_type",
            "product",
            "product_sku",
            "product_name",
            "material",
            "material_sku",
            "material_name",
            "movement",
            "quantity",
            "balance",
            "reason",
            "ref_type",
            "ref_id",
            "notes",
            "created_by",
            "created_at",
        ]


class ManualEntrySerializer(serializers.Serializer):
    product_id = serializers.UUIDField(required=False)
    material_id = serializers.UUIDField(required=False)
    movement = serializers.ChoiceField(choices=["IN", "OUT", "ADJUST"])
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    reason = serializers.ChoiceField(
        choices=["PURCHASE", "MANUAL_ADJUST", "PRODUCTION"],
        default="MANUAL_ADJUST",
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("product_id") and not attrs.get("material_id"):
            raise serializers.ValidationError("Indica product_id o material_id.")
        if attrs.get("product_id") and attrs.get("material_id"):
            raise serializers.ValidationError("Solo uno: producto o material.")
        return attrs

    def validate_quantity(self, value):
        if self.initial_data.get("movement") != "ADJUST" and Decimal(value) <= 0:
            raise serializers.ValidationError("La cantidad debe ser positiva.")
        if self.initial_data.get("movement") == "ADJUST" and Decimal(value) == 0:
            raise serializers.ValidationError("El ajuste no puede ser 0.")
        return value
