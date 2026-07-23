from rest_framework import serializers

from apps.logistics.models import BatchJob, BatchJobItem, Shipment


class ShipmentSerializer(serializers.ModelSerializer):
    sale_external_id = serializers.CharField(source="sale.external_id", read_only=True)
    customer_name = serializers.CharField(source="sale.customer_name", read_only=True)
    address_raw = serializers.CharField(source="sale.address_raw", read_only=True)
    city_raw = serializers.CharField(source="sale.city_raw", read_only=True)
    qty_dorados = serializers.SerializerMethodField()
    qty_plateados = serializers.SerializerMethodField()
    geo_city_name = serializers.CharField(source="geo_city.municipality", read_only=True)
    geo_city_code = serializers.CharField(source="geo_city.municipality_code", read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "id",
            "sale",
            "sale_external_id",
            "customer_name",
            "address_raw",
            "city_raw",
            "address_mirror",
            "city_mirror",
            "state_mirror",
            "geo_city",
            "geo_city_name",
            "geo_city_code",
            "geo_state_code",
            "address_formatted",
            "do_not_ship",
            "status",
            "carrier",
            "service",
            "tracking_number",
            "label_url",
            "shipping_cost",
            "generated_city",
            "generated_state",
            "generated_address",
            "warning",
            "warning_detail",
            "last_error",
            "attempts",
            "sent_at",
            "qty_dorados",
            "qty_plateados",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "sale",
            "geo_city",
            "geo_state_code",
            "address_formatted",
            "do_not_ship",
            "tracking_number",
            "label_url",
            "shipping_cost",
            "generated_city",
            "generated_state",
            "generated_address",
            "warning",
            "warning_detail",
            "last_error",
            "attempts",
            "sent_at",
            "created_at",
            "updated_at",
        ]

    def get_qty_dorados(self, obj) -> int:
        return sum(
            i.quantity for i in obj.sale.items.all() if i.color == "DORADO"
        )

    def get_qty_plateados(self, obj) -> int:
        return sum(
            i.quantity for i in obj.sale.items.all() if i.color == "PLATEADO"
        )


class ShipmentMirrorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ["address_mirror", "city_mirror", "state_mirror", "carrier", "service"]


class IdsSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)


class BatchJobItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BatchJobItem
        fields = ["id", "ref_id", "status", "result", "error", "updated_at"]


class BatchJobSerializer(serializers.ModelSerializer):
    items = BatchJobItemSerializer(many=True, read_only=True)

    class Meta:
        model = BatchJob
        fields = [
            "id",
            "job_type",
            "status",
            "total",
            "done",
            "success",
            "failed",
            "created_at",
            "items",
        ]
