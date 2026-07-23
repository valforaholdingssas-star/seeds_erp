from django.db import models

from apps.common.models import BaseModel


class DocumentKind(models.TextChoices):
    SALE_NOTE = "SALE_NOTE", "Nota de venta"
    PRODUCT = "PRODUCT", "Producto"
    POLICY = "POLICY", "Política"
    SYMPTOM = "SYMPTOM", "Síntoma"
    CASE = "CASE", "Caso"


class Document(BaseModel):
    kind = models.CharField(max_length=32, choices=DocumentKind.choices, db_index=True)
    ref_type = models.CharField(max_length=64, blank=True, default="")
    ref_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    title = models.CharField(max_length=255, blank=True, default="")
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kind", "ref_type"]),
        ]

    def __str__(self) -> str:
        return self.title or f"{self.kind}:{self.id}"


class Embedding(BaseModel):
    """
    Vector storage.
    Uses JSON float list so sandbox PostGIS image works without pgvector.
    When pgvector is available, migrate to VectorField(dimensions=…).
    """

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="embeddings")
    chunk = models.TextField()
    vector = models.JSONField(default=list, blank=True)
    dimensions = models.PositiveIntegerField(default=64)

    class Meta:
        indexes = [
            models.Index(fields=["document"]),
        ]
