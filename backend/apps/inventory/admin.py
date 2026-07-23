from django.contrib import admin

from apps.inventory.models import KardexEntry, Material, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "color", "stock", "reorder_level", "active", "is_generic")
    list_filter = ("color", "active", "is_generic")
    search_fields = ("sku", "name", "woo_product_id")


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "unit", "stock", "active")
    search_fields = ("sku", "name")


@admin.register(KardexEntry)
class KardexEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "movement", "product", "quantity", "balance", "reason", "ref_id")
    list_filter = ("movement", "reason", "item_type")
    search_fields = ("ref_id", "product__sku", "notes")
    readonly_fields = ("created_at", "updated_at")
