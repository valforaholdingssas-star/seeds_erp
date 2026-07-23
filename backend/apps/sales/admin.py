from django.contrib import admin

from apps.sales.models import (
    ConsolidatedSale,
    EcommerceSale,
    FeriaSale,
    KommoSale,
    ManualSale,
    PaymentMethod,
    ProductPackRule,
    SaleItem,
)


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "active", "is_system", "updated_at")
    list_filter = ("active", "is_system")
    search_fields = ("name",)


@admin.register(ConsolidatedSale)
class ConsolidatedSaleAdmin(admin.ModelAdmin):
    list_display = (
        "external_id",
        "source",
        "customer_name",
        "total_value",
        "status",
        "state",
        "seller",
        "closed_at",
    )
    list_filter = ("source", "state", "status", "income_source")
    search_fields = ("external_id", "customer_name", "email", "id_number", "city_raw")
    inlines = [SaleItemInline]


@admin.register(ProductPackRule)
class ProductPackRuleAdmin(admin.ModelAdmin):
    list_display = ("woo_product_id", "name_contains", "multiplier", "active")


admin.site.register(EcommerceSale)
admin.site.register(KommoSale)
admin.site.register(FeriaSale)
admin.site.register(ManualSale)
