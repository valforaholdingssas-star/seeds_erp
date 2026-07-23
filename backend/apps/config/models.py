from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class SettingValue(BaseModel):
    key = models.CharField(max_length=128, unique=True, db_index=True)
    value = models.TextField(blank=True, default="")
    encrypted = models.BinaryField(null=True, blank=True)
    is_secret = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="setting_updates",
    )

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class SettingAuditAction(models.TextChoices):
    CREATED = "CREATED", "Creado"
    UPDATED = "UPDATED", "Actualizado"
    ROTATED = "ROTATED", "Rotado"
    DELETED = "DELETED", "Eliminado"


class SettingAudit(BaseModel):
    key = models.CharField(max_length=128, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="setting_audits",
    )
    action = models.CharField(max_length=16, choices=SettingAuditAction.choices)
    old_value_masked = models.CharField(max_length=64, blank=True)
    new_value_masked = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
