from rest_framework import serializers

from apps.geo.models import GeoCatalog


class GeoCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoCatalog
        fields = [
            "id",
            "municipality",
            "municipality_code",
            "department",
            "department_iso",
            "search",
        ]
