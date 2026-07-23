from django.contrib import admin

from apps.integrations.models import IntegrationLog, RawWebhookEvent


@admin.register(RawWebhookEvent)
class RawWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("received_at", "source", "event_type", "status", "attempts")
    list_filter = ("source", "status")
    search_fields = ("dedupe_key", "error")


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "provider", "method", "response_status", "success")
    list_filter = ("provider", "success")
    search_fields = ("url", "ref_id")
