from __future__ import annotations

from django.db import transaction
from django.db.models import Q

from apps.audit.services import log_audit_event
from apps.sellers.models import Vendedor

SYSTEM_VENDORS = (
    ("ECOMMERCE", True),
    ("FERIAS", True),
)


def normalize_name(value: str) -> str:
    return " ".join((value or "").strip().upper().split())


@transaction.atomic
def ensure_system_vendors(*, actor=None) -> list[Vendedor]:
    created: list[Vendedor] = []
    for name, is_system in SYSTEM_VENDORS:
        obj, was_created = Vendedor.objects.get_or_create(
            name=name,
            defaults={"is_system": is_system, "active": True, "aliases": []},
        )
        if was_created:
            created.append(obj)
            log_audit_event(
                actor=actor,
                action="VENDEDOR_CREATED",
                entity="Vendedor",
                entity_id=str(obj.id),
                metadata={"name": name, "is_system": True},
            )
    return created


def resolve_vendedor(
    commercial_raw: str | None,
    *,
    create_if_missing: bool = True,
    actor=None,
) -> Vendedor | None:
    """
    Resuelve texto crudo → Vendedor por name o aliases.
    Si no existe y create_if_missing=True, crea uno "por revisar".
    Nunca descarta la venta por vendedor desconocido.
    """
    raw = (commercial_raw or "").strip()
    if not raw:
        return None

    needle = normalize_name(raw)

    exact = Vendedor.objects.filter(name__iexact=raw.strip()).first()
    if exact:
        return exact

    # Match aliases (case-insensitive)
    for vendor in Vendedor.objects.filter(active=True):
        aliases = vendor.aliases or []
        if any(normalize_name(a) == needle for a in aliases if isinstance(a, str)):
            return vendor
        if normalize_name(vendor.name) == needle:
            return vendor

    if not create_if_missing:
        return None

    name = raw.strip()
    vendor, created = Vendedor.objects.get_or_create(
        name=name,
        defaults={
            "is_system": False,
            "active": True,
            "aliases": [],
            "needs_review": True,
        },
    )
    if created:
        log_audit_event(
            actor=actor,
            action="VENDEDOR_AUTO_CREATED",
            entity="Vendedor",
            entity_id=str(vendor.id),
            metadata={"name": name, "from": commercial_raw},
        )
    return vendor


def search_vendedores(query: str = ""):
    qs = Vendedor.objects.select_related("user").all()
    if query:
        qs = qs.filter(
            Q(name__icontains=query)
            | Q(aliases__icontains=query)
            | Q(user__email__icontains=query)
            | Q(user__full_name__icontains=query)
        )
    return qs
