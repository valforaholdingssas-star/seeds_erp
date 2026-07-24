from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.audit.services import log_audit_event
from apps.finance.models import (
    BankMovement,
    ClassificationRule,
    MovementStatus,
)


def match_rule(movement: BankMovement, rule: ClassificationRule) -> bool:
    if not rule.active:
        return False
    if rule.bank_id and rule.bank_id != movement.bank_id:
        return False
    needle = (rule.concept_contains or "").strip().upper()
    if not needle:
        return False
    return needle in (movement.concept or "").upper()


def best_rule(movement: BankMovement) -> ClassificationRule | None:
    rules = (
        ClassificationRule.objects.filter(active=True)
        .select_related("financial_account", "accounting_account", "bank")
        .order_by("priority", "name")
    )
    for rule in rules:
        if match_rule(movement, rule):
            return rule
    return None


def apply_rules_to_movement(movement: BankMovement, *, save: bool = True) -> ClassificationRule | None:
    rule = best_rule(movement)
    if not rule or not rule.auto_apply:
        return rule
    movement.financial_account = rule.financial_account
    movement.accounting_account = rule.accounting_account
    if rule.attribution:
        movement.attribution = rule.attribution
    movement.is_interbank = bool(rule.is_interbank)
    if rule.financial_account_id or rule.is_interbank:
        movement.status = MovementStatus.CLASIFICADO
    if save and movement.pk:
        movement.save()
    return rule


@transaction.atomic
def classify_movements(
    *,
    ids: list,
    financial_account_id=None,
    accounting_account_id=None,
    attribution: str = "",
    is_interbank: bool | None = None,
    status: str | None = None,
    actor=None,
) -> int:
    qs = BankMovement.objects.select_for_update().filter(id__in=ids)
    n = 0
    for mov in qs:
        if financial_account_id is not None:
            mov.financial_account_id = financial_account_id or None
        if accounting_account_id is not None:
            mov.accounting_account_id = accounting_account_id or None
        if attribution is not None and attribution != "":
            mov.attribution = attribution
        if is_interbank is not None:
            mov.is_interbank = is_interbank
        if status:
            mov.status = status
        elif mov.financial_account_id or mov.is_interbank:
            mov.status = MovementStatus.CLASIFICADO
        mov.save()
        n += 1
        log_audit_event(
            actor=actor,
            action="BANK_MOVEMENT_CLASSIFY",
            entity="BankMovement",
            entity_id=str(mov.id),
            metadata={
                "efe": str(mov.financial_account_id or ""),
                "puc": str(mov.accounting_account_id or ""),
                "interbank": mov.is_interbank,
            },
        )
    return n


def classification_kpi(*, year: int, month: int) -> dict:
    qs = BankMovement.objects.filter(date__year=year, date__month=month)
    total = qs.count()
    classified = qs.exclude(status=MovementStatus.POR_CLASIFICAR).count()
    by_item = {
        row["item"]: row["c"]
        for row in qs.values("item").annotate(c=Count("id"))
    }
    pct = round((classified / total) * 100, 2) if total else 100.0
    return {
        "year": year,
        "month": month,
        "total": total,
        "classified": classified,
        "pending": total - classified,
        "pct_classified": pct,
        "by_item": by_item,
        "as_of": timezone.now().isoformat(),
    }
