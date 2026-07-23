from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.sellers.models import Vendedor

User = get_user_model()


class VendedorUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "full_name", "email"]


class VendedorSerializer(serializers.ModelSerializer):
    user_detail = VendedorUserSerializer(source="user", read_only=True)

    class Meta:
        model = Vendedor
        fields = [
            "id",
            "name",
            "user",
            "user_detail",
            "is_system",
            "active",
            "aliases",
            "needs_review",
            "monthly_goal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "user_detail"]

    def validate_name(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        qs = Vendedor.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un vendedor con ese nombre.")
        return value

    def validate_aliases(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("aliases debe ser una lista.")
        cleaned = []
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError("Cada alias debe ser texto.")
            item = item.strip()
            if item:
                cleaned.append(item)
        return cleaned

    def validate(self, attrs):
        instance = self.instance
        is_system = attrs.get("is_system", getattr(instance, "is_system", False))
        if instance and instance.is_system:
            # No permitir renombrar ni desmarcar system en ECOMMERCE/FERIAS
            if "name" in attrs and attrs["name"] != instance.name:
                raise serializers.ValidationError(
                    {"name": "No puedes renombrar un vendedor de sistema."}
                )
            if "is_system" in attrs and attrs["is_system"] is False:
                raise serializers.ValidationError(
                    {"is_system": "No puedes quitar la marca de sistema."}
                )
        if is_system and attrs.get("user"):
            raise serializers.ValidationError(
                {"user": "Los vendedores de sistema no se vinculan a un usuario."}
            )
        return attrs
