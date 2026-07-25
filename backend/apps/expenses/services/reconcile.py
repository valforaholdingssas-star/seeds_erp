from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models.functions import Abs
from django.utils.dateparse import parse_date

from apps.expenses.models import Expense
from apps.finance.models import BankMovement, MovementItem, MovementStatus


def suggest_movements(expense: Expense, *, days: int = 7, limit: int = 20) -> list[BankMovement]:
    if not expense.bank_account_id or expense.amount is None:
        return []
    amount = abs(Decimal(expense.amount or 0))
    qs = (
        BankMovement.objects.filter(
            bank_id=expense.bank_account_id,
            item=MovementItem.EGRESO,
        )
        .annotate(abs_value=Abs("value"))
        .filter(abs_value=amount)
    )
    if expense.expense_date:
        start = expense.expense_date - timedelta(days=days)
        end = expense.expense_date + timedelta(days=days)
        qs = qs.filter(date__gte=start, date__lte=end)
    linked = (
        Expense.objects.exclude(pk=expense.pk)
        .exclude(bank_movement_id=None)
        .values_list("bank_movement_id", flat=True)
    )
    qs = qs.exclude(id__in=linked)
    return list(qs.select_related("bank", "financial_account").order_by("-date")[:limit])


def reconcile_expense(expense: Expense, movement: BankMovement, *, actor=None) -> Expense:
    if expense.bank_account_id and movement.bank_id != expense.bank_account_id:
        raise ValueError("El movimiento pertenece a otro banco.")
    expense.bank_movement = movement
    expense.reconciled = True
    if not expense.payment_date:
        expense.payment_date = movement.date
    expense.save(
        update_fields=["bank_movement", "reconciled", "payment_date", "updated_at"]
    )
    if movement.status in {MovementStatus.CLASIFICADO, MovementStatus.POR_CLASIFICAR}:
        movement.status = MovementStatus.CONCILIADO
        movement.save(update_fields=["status", "updated_at"])
    return expense


def parse_optional_date(value):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value
    return parse_date(str(value))
