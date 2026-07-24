from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce, TruncDate

from apps.config import settings_service as cfg
from apps.finance.models import Bank, BankMovement, MovementItem
from apps.sales.models import ConsolidatedSale, SaleState


def _tolerance() -> Decimal:
    raw = cfg.get("finance.audit_tolerance", 1000)
    try:
        return Decimal(str(raw or 1000))
    except Exception:
        return Decimal("1000")


def _bank_alias_map() -> dict[str, Bank]:
    mapping: dict[str, Bank] = {}
    for bank in Bank.objects.filter(active=True):
        mapping[bank.name.strip().upper()] = bank
        for alias in bank.report_aliases or []:
            if alias:
                mapping[str(alias).strip().upper()] = bank
    return mapping


def build_income_audit(*, year: int, month: int, bank_name: str | None = None) -> dict:
    """
    VALIDACIÓN = INGRESO NETO bancos − INGRESO reportes
    INGRESO NETO = ingresos banco − ingresos interbancarios
    """
    alias_map = _bank_alias_map()
    banks_qs = Bank.objects.filter(active=True)
    if bank_name:
        banks_qs = banks_qs.filter(name__iexact=bank_name)
    banks = list(banks_qs.order_by("name"))
    bank_names = {b.name for b in banks}

    reports: dict[tuple[str, date], Decimal] = defaultdict(lambda: Decimal("0"))
    unmapped: list[dict] = []
    sales = (
        ConsolidatedSale.objects.filter(state=SaleState.ACTIVE)
        .annotate(day=TruncDate(Coalesce("closed_at", "created_at")))
        .filter(day__year=year, day__month=month)
        .only("id", "payment_account", "total_value", "external_id")
    )
    for sale in sales.iterator():
        day = getattr(sale, "day", None)
        if not day:
            continue
        label = (sale.payment_account or "").strip()
        bank = alias_map.get(label.upper()) if label else None
        if not bank or bank.name not in bank_names:
            unmapped.append(
                {
                    "sale_id": str(sale.id),
                    "external_id": sale.external_id,
                    "payment_account": label,
                    "value": str(sale.total_value),
                    "date": day.isoformat(),
                }
            )
            continue
        reports[(bank.name, day)] += Decimal(sale.total_value or 0)

    bank_gross: dict[tuple[str, date], Decimal] = defaultdict(lambda: Decimal("0"))
    bank_inter: dict[tuple[str, date], Decimal] = defaultdict(lambda: Decimal("0"))
    mov_qs = BankMovement.objects.filter(
        date__year=year,
        date__month=month,
        item=MovementItem.INGRESO,
        bank__in=banks,
    )
    for row in mov_qs.values("bank__name", "date", "is_interbank").annotate(total=Sum("value")):
        key = (row["bank__name"], row["date"])
        total = Decimal(row["total"] or 0)
        bank_gross[key] += total
        if row["is_interbank"]:
            bank_inter[key] += total

    days = sorted(
        {
            *[d for (_, d) in reports.keys()],
            *[d for (_, d) in bank_gross.keys()],
        }
    )

    tol = _tolerance()
    rows = []
    chart_by_bank: dict[str, list] = {b.name: [] for b in banks}
    for bank in banks:
        for d in days:
            key = (bank.name, d)
            reported = reports.get(key, Decimal("0"))
            all_in = bank_gross.get(key, Decimal("0"))
            inter_only = bank_inter.get(key, Decimal("0"))
            net = all_in - inter_only
            validation = net - reported
            if reported == 0 and all_in == 0 and inter_only == 0:
                continue
            out_of_tol = abs(validation) > tol
            row = {
                "bank": bank.name,
                "date": d.isoformat(),
                "reports": str(reported),
                "banks_gross": str(all_in),
                "interbank": str(inter_only),
                "banks_net": str(net),
                "validation": str(validation),
                "out_of_tolerance": out_of_tol,
            }
            rows.append(row)
            chart_by_bank[bank.name].append(
                {
                    "date": d.isoformat(),
                    "label": f"{d.day:02d}",
                    "validation": float(validation),
                    "out_of_tolerance": out_of_tol,
                }
            )

    totals = []
    for bank in banks:
        bank_rows = [r for r in rows if r["bank"] == bank.name]
        totals.append(
            {
                "bank": bank.name,
                "reports": str(sum((Decimal(r["reports"]) for r in bank_rows), Decimal("0"))),
                "banks_net": str(sum((Decimal(r["banks_net"]) for r in bank_rows), Decimal("0"))),
                "validation": str(
                    sum((Decimal(r["validation"]) for r in bank_rows), Decimal("0"))
                ),
                "out_of_tolerance_days": sum(1 for r in bank_rows if r["out_of_tolerance"]),
            }
        )

    return {
        "year": year,
        "month": month,
        "tolerance": str(tol),
        "banks": [b.name for b in banks],
        "rows": rows,
        "totals": totals,
        "chart": chart_by_bank,
        "unmapped_reports": unmapped[:100],
        "unmapped_count": len(unmapped),
    }
