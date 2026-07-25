from rest_framework import serializers

from apps.dashboard.models import ControlIndicator, IndicatorSnapshot


class ControlIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlIndicator
        fields = [
            "id",
            "key",
            "label",
            "module",
            "description",
            "unit",
            "severity",
            "warn_threshold",
            "crit_threshold",
            "target_url",
            "visible",
            "roles",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["key"]


class IndicatorSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndicatorSnapshot
        fields = ["id", "value", "amount", "captured_at"]
