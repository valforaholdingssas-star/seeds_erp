from rest_framework import serializers

from apps.integrations.models import RawWebhookEvent


class RawWebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawWebhookEvent
        fields = [
            "id",
            "source",
            "event_type",
            "received_at",
            "status",
            "error",
            "attempts",
            "processed_at",
            "dedupe_key",
        ]
