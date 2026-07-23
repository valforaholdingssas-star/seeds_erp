from django.contrib import admin

from apps.sellers.models import Vendedor


@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "is_system",
        "active",
        "needs_review",
        "monthly_goal",
        "user",
        "updated_at",
    )
    list_filter = ("is_system", "active", "needs_review")
    search_fields = ("name", "aliases")
    raw_id_fields = ("user",)
