from django.contrib import admin

from apps.config.models import SettingAudit, SettingValue


@admin.register(SettingValue)
class SettingValueAdmin(admin.ModelAdmin):
    list_display = ("key", "is_secret", "version", "updated_at", "updated_by")
    search_fields = ("key",)
    readonly_fields = ("encrypted", "version", "updated_at", "created_at")


@admin.register(SettingAudit)
class SettingAuditAdmin(admin.ModelAdmin):
    list_display = ("created_at", "key", "action", "actor")
    list_filter = ("action",)
    search_fields = ("key",)
