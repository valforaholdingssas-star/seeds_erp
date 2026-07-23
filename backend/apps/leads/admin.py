from django.contrib import admin

from apps.leads.models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "source", "city", "seller", "created_at")
    list_filter = ("status", "source")
    search_fields = ("name", "email", "phone", "city")
