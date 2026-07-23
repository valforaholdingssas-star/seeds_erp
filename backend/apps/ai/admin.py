from django.contrib import admin

from apps.ai.models import Document, Embedding


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "ref_type", "ref_id", "created_at")
    list_filter = ("kind",)
    search_fields = ("title", "content", "ref_id")


@admin.register(Embedding)
class EmbeddingAdmin(admin.ModelAdmin):
    list_display = ("document", "dimensions", "created_at")
    search_fields = ("chunk",)
