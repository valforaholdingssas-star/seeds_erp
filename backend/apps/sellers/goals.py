from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.sellers.models import SellerMonthlyGoal, Vendedor

MONTHS = list(range(1, 13))


def get_goal_for_month(*, seller_id: str | None, year: int, month: int) -> Decimal | None:
    if not seller_id or month < 1 or month > 12:
        return None
    row = (
        SellerMonthlyGoal.objects.filter(seller_id=seller_id, year=year, month=month)
        .only("amount")
        .first()
    )
    if row is None:
        return None
    return Decimal(row.amount)


def goals_matrix(*, year: int) -> dict:
    sellers = list(
        Vendedor.objects.filter(active=True, is_system=False)
        .order_by("name")
        .values("id", "name")
    )
    goals = {
        (str(g.seller_id), g.month): g.amount
        for g in SellerMonthlyGoal.objects.filter(year=year).only(
            "seller_id", "month", "amount"
        )
    }
    rows = []
    for s in sellers:
        sid = str(s["id"])
        months: dict[str, str | None] = {}
        year_total = Decimal("0")
        for m in MONTHS:
            amount = goals.get((sid, m))
            months[str(m)] = str(amount) if amount is not None else None
            if amount is not None:
                year_total += Decimal(amount)
        rows.append(
            {
                "seller_id": sid,
                "seller_name": s["name"],
                "months": months,
                "year_total": str(year_total),
            }
        )
    return {"year": year, "sellers": rows}


@transaction.atomic
def upsert_goals(*, year: int, items: list[dict]) -> dict:
    """
    items: [{seller_id, month, amount}]
    amount null / "" → delete that cell
    """
    saved = 0
    deleted = 0
    for item in items:
        seller_id = str(item.get("seller_id") or "").strip()
        try:
            month = int(item.get("month") or 0)
        except (TypeError, ValueError):
            continue
        if not seller_id or month < 1 or month > 12:
            continue
        if not Vendedor.objects.filter(id=seller_id).exists():
            continue

        raw = item.get("amount", None)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            deleted += SellerMonthlyGoal.objects.filter(
                seller_id=seller_id, year=year, month=month
            ).delete()[0]
            continue

        try:
            amount = Decimal(str(raw).replace(",", "").strip())
        except (InvalidOperation, TypeError, ValueError):
            continue
        if amount < 0:
            amount = Decimal("0")

        SellerMonthlyGoal.objects.update_or_create(
            seller_id=seller_id,
            year=year,
            month=month,
            defaults={"amount": amount},
        )
        saved += 1

    return {"year": year, "saved": saved, "deleted": deleted, **goals_matrix(year=year)}
