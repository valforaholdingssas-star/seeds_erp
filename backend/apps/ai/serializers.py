from rest_framework import serializers

from apps.ai.models import Document, DocumentKind


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "kind",
            "ref_type",
            "ref_id",
            "title",
            "content",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_kind(self, value: str) -> str:
        if value not in DocumentKind.values:
            raise serializers.ValidationError("kind inválido.")
        return value

    def validate_content(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("content es obligatorio.")
        return value


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=2000)

    def validate_question(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Escribe una pregunta.")
        return value


class SearchSerializer(serializers.Serializer):
    q = serializers.CharField(max_length=1000)
    kind = serializers.ChoiceField(choices=DocumentKind.choices, required=False, allow_blank=True)
    limit = serializers.IntegerField(min_value=1, max_value=20, default=5)
