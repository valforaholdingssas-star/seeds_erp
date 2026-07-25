from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.expenses.models import Expense, ExpenseAmortizationEntry
from apps.finance.models import EfeMonthClose


def amortization_periods(expense: Expense) -> int:
    if expense.amortize and expense.amortization_months and expense.amortization_months >= 1:
        return int(expense.amortization_months)
    return 1


def _add_months(start: date, months: int) -> date:
    y = start.year + (start.month - 1 + months) // 12
    m = (start.month - 1 + months) % 12 + 1
    d = min(start.day, monthrange(y, m)[1])
    return date(y, m, d)


def split_amount(total: Decimal, n: int) -> list[Decimal]:
    if n < 1:
        n = 1
    total = Decimal(total or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if n == 1:
        return [total]
    base = (total / Decimal(n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    parts = [base] * n
    diff = total - sum(parts)
    parts[-1] = (parts[-1] + diff).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return parts


def closed_months_for_entries(entries: list[tuple[int, int]]) -> list[str]:
    if not entries:
        return []
    years = {y for y, _ in entries}
    closed = {
        (c.year, c.month)
        for c in EfeMonthClose.objects.filter(year__in=years)
    }
    return [f"{y:04d}-{m:02d}" for y, m in entries if (y, m) in closed]


@transaction.atomic
def regenerate_amortization(
    expense: Expense,
    *,
    allow_closed: bool = False,
) -> dict:
    """
    Rebuild amortization entries for an expense that feeds the EFE.
    Clears entries when the expense no longer feeds EFE or lacks efe_account.
    """
    ExpenseAmortizationEntry.objects.filter(expense=expense).delete()

    status = expense.status
    if not status or not status.feeds_efe or not expense.efe_account_id:
        return {"entries": 0, "closed_months": [], "cleared": True}

    n = amortization_periods(expense)
    start = expense.expense_date
    parts = split_amount(Decimal(expense.amount or 0), n)
    planned: list[tuple[int, int, Decimal]] = []
    for i, amt in enumerate(parts):
        period = _add_months(start, i)
        planned.append((period.year, period.month, amt))

    closed = closed_months_for_entries([(y, m) for y, m, _ in planned])
    if closed and not allow_closed:
        raise ValueError(
            "La amortización afecta meses EFE cerrados: "
            + ", ".join(closed)
            + ". Reabre el mes o confirma con allow_closed."
        )

    objs = [
        ExpenseAmortizationEntry(
            expense=expense,
            period_year=y,
            period_month=m,
            amount=amt,
            efe_account_id=expense.efe_account_id,
        )
        for y, m, amt in planned
    ]
    ExpenseAmortizationEntry.objects.bulk_create(objs)
    return {
        "entries": len(objs),
        "closed_months": closed,
        "cleared": False,
        "n": n,
    }
