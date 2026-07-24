from django.contrib.auth import authenticate
from rest_framework import serializers

from apps.users.models import Role, User, UserStatus
from apps.users.module_access import (
    ALL_MODULE_KEYS,
    MODULE_CATALOG,
    default_modules_for_role,
    user_effective_modules,
)


class UserSerializer(serializers.ModelSerializer):
    modules_effective = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "id_type",
            "id_number",
            "role",
            "status",
            "modules",
            "modules_effective",
            "created_at",
            "last_login_at",
        ]
        read_only_fields = ["id", "created_at", "last_login_at", "modules_effective"]

    def get_modules_effective(self, obj) -> list[str]:
        return user_effective_modules(obj)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    modules = serializers.ListField(
        child=serializers.ChoiceField(choices=ALL_MODULE_KEYS),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "id_type",
            "id_number",
            "role",
            "status",
            "modules",
            "password",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, min_length=8, required=False, allow_blank=False
    )
    modules = serializers.ListField(
        child=serializers.ChoiceField(choices=ALL_MODULE_KEYS),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = User
        fields = [
            "full_name",
            "phone",
            "id_type",
            "id_number",
            "role",
            "status",
            "modules",
            "password",
        ]

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("Email o contraseña incorrectos.")
        if user.status != UserStatus.ACTIVE:
            raise serializers.ValidationError("La cuenta está suspendida.")
        attrs["user"] = user
        return attrs


class RoleChoicesSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


def role_choices() -> list[dict[str, str]]:
    return [{"value": value, "label": label} for value, label in Role.choices]


def modules_catalog_payload() -> dict:
    return {
        "modules": MODULE_CATALOG,
        "role_defaults": {
            role: default_modules_for_role(role) for role, _ in Role.choices
        },
    }


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=64)
    password = serializers.CharField(write_only=True, min_length=8)
