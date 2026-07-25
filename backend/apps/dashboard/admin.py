from django.contrib import admin

from apps.dashboard.models import ControlIndicator, IndicatorSnapshot


@admin.register(ControlIndicator)
class ControlIndicatorAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "module", "severity", "visible", "order")
    list_filter = ("module", "severity", "visible")
    search_fields = ("key", "label")


@admin.register(IndicatorSnapshot)
class IndicatorSnapshotAdmin(admin.ModelAdmin):
    list_display = ("indicator", "value", "amount", "captured_at")
    list_filter = ("indicator__module",)
