from __future__ import annotations

from django.db import transaction
from django.db.models import Q

from apps.audit.services import log_audit_event
from apps.sales.models import (
    ConsolidatedSale,
    EcommerceSale,
    FeriaSale,
    KommoSale,
    ManualSale,
    PaymentMethod,
)

DEFAULT_PAYMENT_METHODS = (
    ("Nequi", ["nequi"], True),
    ("Efectivo", ["cash", "efectivo"], True),
    ("Mercadopago", ["mercadopago", "mercado pago", "mp"], True),
    ("Bancolombia Seeds", ["bancolombia", "bancolombia seeds"], True),
    ("Tarjeta (Bold)", ["bold", "tarjeta", "tarjeta (bold)", "card"], True),
)


def normalize_payment_name(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


@transaction.atomic
def ensure_default_payment_methods(*, actor=None) -> list[PaymentMethod]:
    created: list[PaymentMethod] = []
    for name, aliases, is_system in DEFAULT_PAYMENT_METHODS:
        obj, was_created = PaymentMethod.objects.get_or_create(
            name=name,
            defaults={"active": True, "aliases": aliases, "is_system": is_system},
        )
        if was_created:
            created.append(obj)
            log_audit_event(
                actor=actor,
                action="PAYMENT_METHOD_CREATED",
                entity="PaymentMethod",
                entity_id=str(obj.id),
                metadata={"name": name, "seed": True},
            )
    return created


def resolve_payment_method(
    raw: str | None,
    *,
    create_if_missing: bool = True,
    actor=None,
) -> PaymentMethod | None:
    """
    Resuelve texto crudo (Woo/Kommo/CSV) → PaymentMethod.
    Si no existe y create_if_missing, crea uno activo con ese nombre.
    """
    text = (raw or "").strip()
    if not text:
        return None

    needle = normalize_payment_name(text)
    exact = PaymentMethod.objects.filter(name__iexact=text).first()
    if exact:
        return exact

    for method in PaymentMethod.objects.filter(active=True):
        if normalize_payment_name(method.name) == needle:
            return method
        aliases = method.aliases or []
        if any(normalize_payment_name(a) == needle for a in aliases if isinstance(a, str)):
            return method

    if not create_if_missing:
        return None

    method, created = PaymentMethod.objects.get_or_create(
        name=text,
        defaults={"active": True, "aliases": [], "is_system": False},
    )
    if created:
        log_audit_event(
            actor=actor,
            action="PAYMENT_METHOD_AUTO_CREATED",
            entity="PaymentMethod",
            entity_id=str(method.id),
            metadata={"name": text, "from": raw},
        )
    return method


def apply_payment_method_name(method: PaymentMethod) -> int:
    """Propaga el nombre actual a payment_account denormalizado en ventas."""
    updated = 0
    updated += ConsolidatedSale.objects.filter(payment_method=method).exclude(
        payment_account=method.name
    ).update(payment_account=method.name)
    for model in (EcommerceSale, KommoSale, FeriaSale, ManualSale):
        updated += model.objects.filter(payment_method=method).exclude(
            payment_account=method.name
        ).update(payment_account=method.name)
    return updated


def backfill_payment_methods_from_accounts(*, actor=None) -> dict:
    """Crea PaymentMethod desde payment_account distintos y enlaza ventas."""
    ensure_default_payment_methods(actor=actor)
    names = set(
        ConsolidatedSale.objects.exclude(payment_account="")
        .values_list("payment_account", flat=True)
        .distinct()
    )
    for model in (EcommerceSale, KommoSale, FeriaSale, ManualSale):
        names.update(
            model.objects.exclude(payment_account="")
            .values_list("payment_account", flat=True)
            .distinct()
        )

    linked = 0
    for name in sorted(n for n in names if n and str(n).strip()):
        method = resolve_payment_method(str(name), create_if_missing=True, actor=actor)
        if not method:
            continue
        linked += ConsolidatedSale.objects.filter(
            payment_account=name, payment_method__isnull=True
        ).update(payment_method=method, payment_account=method.name)
        for model in (EcommerceSale, KommoSale, FeriaSale, ManualSale):
            linked += model.objects.filter(
                payment_account=name, payment_method__isnull=True
            ).update(payment_method=method, payment_account=method.name)

    return {"methods": PaymentMethod.objects.count(), "linked_rows": linked}


def search_payment_methods(query: str = ""):
    qs = PaymentMethod.objects.all()
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(aliases__icontains=query))
    return qs
