from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    VENTAS = "VENTAS", "Ventas"
    LOGISTICA = "LOGISTICA", "Logística"
    CONTABILIDAD = "CONTABILIDAD", "Contabilidad"
    SUPERVISOR = "SUPERVISOR", "Supervisor"
    VIEWER = "VIEWER", "Solo lectura"


class UserStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Activo"
    SUSPENDED = "SUSPENDED", "Suspendido"


PASSWORD_RESET_TTL = timedelta(hours=1)


class UserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.ADMIN)
        extra_fields.setdefault("status", UserStatus.ACTIVE)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    id_type = models.CharField(max_length=16, blank=True, default="CC")
    id_number = models.CharField(max_length=32, blank=True, db_index=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.VIEWER)
    status = models.CharField(
        max_length=16, choices=UserStatus.choices, default=UserStatus.ACTIVE
    )
    # Empty list = use role defaults. Non-empty = explicit module keys (see module_access.py).
    modules = models.JSONField(default=list, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["role", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"

    def save(self, *args, **kwargs):
        self.is_active = self.status == UserStatus.ACTIVE
        super().save(*args, **kwargs)

    def mark_login(self) -> None:
        self.last_login_at = timezone.now()
        self.save(update_fields=["last_login_at", "updated_at"])


class PasswordResetToken(models.Model):
    """One-time token for password recovery (email lookup, not user FK)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"PasswordResetToken<{self.email}>"

    @classmethod
    def issue(cls, email: str) -> PasswordResetToken:
        email = User.objects.normalize_email(email)
        return cls.objects.create(
            email=email,
            token=secrets.token_urlsafe(32),
            expires_at=timezone.now() + PASSWORD_RESET_TTL,
        )

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
