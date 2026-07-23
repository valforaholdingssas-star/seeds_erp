from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from apps.geo.models import GeoCatalog


@admin.register(GeoCatalog)
class GeoCatalogAdmin(GISModelAdmin):
    list_display = ("municipality", "municipality_code", "department", "department_iso")
    search_fields = ("municipality", "municipality_code", "department", "search")
    list_filter = ("department_iso",)
