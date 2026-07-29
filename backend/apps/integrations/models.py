from django.db import models

from apps.common.models import BaseModel


class IntegrationSource(models.TextChoices):
    WOOCOMMERCE = "WOOCOMMERCE", "WooCommerce"
    SHOPIFY = "SHOPIFY", "Shopify"
    KOMMO = "KOMMO", "Kommo"
    ENVIA = "ENVIA", "Envia"
    ALEGRA = "ALEGRA", "Alegra"
    AI = "AI", "IA"
    INTERNAL = "INTERNAL", "Interno"


class RawEventStatus(models.TextChoices):
    RECEIVED = "RECEIVED", "Recibido"
    PROCESSED = "PROCESSED", "Procesado"
    FAILED = "FAILED", "Fallido"
    IGNORED = "IGNORED", "Ignorado"


class RawWebhookEvent(BaseModel):
    source = models.CharField(max_length=32, choices=IntegrationSource.choices, db_index=True)
    event_type = models.CharField(max_length=64, db_index=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    headers = models.JSONField(default=dict, blank=True)
    payload = models.JSONField(default=dict)
    signature = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=16,
        choices=RawEventStatus.choices,
        default=RawEventStatus.RECEIVED,
        db_index=True,
    )
    error = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    processed_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["source", "status"]),
            models.Index(fields=["event_type", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.source}:{self.event_type}:{self.status}"


class IntegrationLog(BaseModel):
    provider = models.CharField(max_length=32, choices=IntegrationSource.choices, db_index=True)
    method = models.CharField(max_length=16, default="POST")
    url = models.TextField()
    request_headers = models.JSONField(default=dict, blank=True)
    request_body = models.JSONField(default=dict, blank=True)
    response_status = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.JSONField(default=dict, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    ref_type = models.CharField(max_length=64, blank=True)
    ref_id = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
