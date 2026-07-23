from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.users.models import Role, UserStatus

User = get_user_model()


class Command(BaseCommand):
    help = "Crea el usuario admin inicial desde variables de entorno (idempotente)."

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@seeds.co")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin1234")
        name = os.environ.get("DJANGO_SUPERUSER_NAME", "Admin Seeds")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": name,
                "role": Role.ADMIN,
                "status": UserStatus.ACTIVE,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Admin creado: {email}"))
        else:
            # Ensure admin flags
            changed = False
            if user.role != Role.ADMIN:
                user.role = Role.ADMIN
                changed = True
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if changed:
                user.save()
            self.stdout.write(self.style.WARNING(f"Admin ya existía: {email}"))
