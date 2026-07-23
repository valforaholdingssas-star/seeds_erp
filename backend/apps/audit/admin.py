from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "entity", "entity_id", "actor")
    list_filter = ("action", "entity")
    search_fields = ("entity_id", "action")
    readonly_fields = ("id", "created_at", "updated_at")
