from django.contrib import admin

from apps.logistics.models import BatchJob, BatchJobItem, Shipment


class BatchItemInline(admin.TabularInline):
    model = BatchJobItem
    extra = 0


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "tracking_number",
        "city_mirror",
        "warning",
        "shipping_cost",
    )
    list_filter = ("status", "warning", "do_not_ship")
    search_fields = ("tracking_number", "sale__external_id", "city_mirror")


@admin.register(BatchJob)
class BatchJobAdmin(admin.ModelAdmin):
    list_display = ("id", "job_type", "status", "total", "done", "success", "failed")
    inlines = [BatchItemInline]
