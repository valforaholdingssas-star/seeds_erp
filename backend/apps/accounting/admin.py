from django.contrib import admin

from apps.accounting.models import Customer, Invoice, Refund


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "id_type", "id_number", "alegra_synced", "alegra_id")
    search_fields = ("name", "id_number", "email")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("idempotency_key", "status", "number", "total", "iva", "attempts")
    list_filter = ("status",)
    search_fields = ("number", "alegra_id", "idempotency_key")


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "manual_void_pending", "alegra_credit_note_id", "created_at")
    list_filter = ("status", "manual_void_pending")
