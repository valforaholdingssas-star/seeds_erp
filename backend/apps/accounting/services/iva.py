from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from apps.accounting.models import Invoice, InvoiceStatus
from apps.expenses.models import Expense, ExpenseNature
from apps.sales.models import ConsolidatedSale, SaleState

CUATRIMESTRES = (
    (1, 4, "Ene–Abr"),
    (5, 8, "May–Ago"),
    (9, 12, "Sep–Dic"),
)


def _d(value) -> str:
    return str(value if value is not None else Decimal("0"))


def _period_bounds(year: int, month_start: int, month_end: int) -> tuple[date, date]:
    start = date(year, month_start, 1)
    end = date(year, month_end, monthrange(year, month_end)[1])
    return start, end


def build_iva_dashboard(*, year: int | None = None, date_from: date | None = None, date_to: date | None = None) -> dict:
    """IVA recaudado (ventas), facturado (facturas GENERADA), cuatrimestres y descontable."""
    today = date.today()
    year = year or today.year

    sales = ConsolidatedSale.objects.filter(state=SaleState.ACTIVE)
    invoices = Invoice.objects.filter(status=InvoiceStatus.GENERADA)
    if date_from:
        sales = sales.filter(closed_at__date__gte=date_from)
        invoices = invoices.filter(confirmed_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(closed_at__date__lte=date_to)
        invoices = invoices.filter(confirmed_at__date__lte=date_to)

    sales_agg = sales.aggregate(
        iva=Coalesce(Sum("iva_generated"), Decimal("0")),
        net=Coalesce(Sum("net_value"), Decimal("0")),
        total=Coalesce(Sum("total_value"), Decimal("0")),
        count=Count("id"),
    )
    inv_agg = invoices.aggregate(
        iva=Coalesce(Sum("iva"), Decimal("0")),
        total=Coalesce(Sum("total"), Decimal("0")),
        count=Count("id"),
    )

    cuatrimestres: list[dict] = []
    for month_start, month_end, label in CUATRIMESTRES:
        start, end = _period_bounds(year, month_start, month_end)
        period_sales = ConsolidatedSale.objects.filter(
            state=SaleState.ACTIVE,
            closed_at__date__gte=start,
            closed_at__date__lte=end,
        ).aggregate(
            iva=Coalesce(Sum("iva_generated"), Decimal("0")),
            count=Count("id"),
        )
        period_inv = Invoice.objects.filter(
            status=InvoiceStatus.GENERADA,
            confirmed_at__date__gte=start,
            confirmed_at__date__lte=end,
        ).aggregate(
            iva=Coalesce(Sum("iva"), Decimal("0")),
            total=Coalesce(Sum("total"), Decimal("0")),
            count=Count("id"),
        )
        iva_facturado = period_inv["iva"] or Decimal("0")
        iva_recaudado = period_sales["iva"] or Decimal("0")
        is_current = start <= today <= end
        is_past = end < today
        cuatrimestres.append(
            {
                "key": f"{year}-C{(month_start - 1) // 4 + 1}",
                "label": f"{label} {year}",
                "year": year,
                "from": start.isoformat(),
                "to": end.isoformat(),
                "is_current": is_current,
                "is_past": is_past,
                "iva_recaudado": _d(iva_recaudado),
                "iva_facturado": _d(iva_facturado),
                "a_pagar": _d(iva_facturado),  # descontable se aplica aparte (no cuatrimestral)
                "sales_count": period_sales["count"] or 0,
                "invoices_count": period_inv["count"] or 0,
                "invoices_total": _d(period_inv["total"]),
            }
        )

    deductible_base = Expense.objects.filter(
        nature=ExpenseNature.EMPRESA,
        iva_discountable__isnull=False,
    ).exclude(iva_discountable=0)
    available = deductible_base.filter(iva_already_discounted=False).aggregate(
        iva=Coalesce(Sum("iva_discountable"), Decimal("0")),
        count=Count("id"),
    )
    used = deductible_base.filter(iva_already_discounted=True).aggregate(
        iva=Coalesce(Sum("iva_discountable"), Decimal("0")),
        count=Count("id"),
    )
    items = list(
        deductible_base.filter(iva_already_discounted=False)
        .order_by("-expense_date", "-created_at")
        .values(
            "id",
            "title",
            "expense_date",
            "amount",
            "iva_discountable",
            "iva_already_discounted",
            "on_behalf_of",
            "concept",
        )[:200]
    )
    for row in items:
        row["id"] = str(row["id"])
        row["expense_date"] = row["expense_date"].isoformat() if row["expense_date"] else None
        row["amount"] = _d(row["amount"])
        row["iva_discountable"] = _d(row["iva_discountable"])
        row["provider_name"] = row.pop("on_behalf_of", "") or row.get("concept") or ""
        row.pop("concept", None)

    current = next((c for c in cuatrimestres if c["is_current"]), cuatrimestres[0] if cuatrimestres else None)

    return {
        "year": year,
        "from": date_from.isoformat() if date_from else None,
        "to": date_to.isoformat() if date_to else None,
        "iva_recaudado": {
            "label": "IVA recaudado",
            "hint": "IVA contenido en ventas activas del rango (aún sin exigir factura).",
            "amount": _d(sales_agg["iva"]),
            "net_value": _d(sales_agg["net"]),
            "total_value": _d(sales_agg["total"]),
            "count": sales_agg["count"] or 0,
        },
        "iva_facturado": {
            "label": "IVA facturado",
            "hint": "IVA de facturas GENERADA en Alegra (confirmed_at). Es lo que cuenta para DIAN.",
            "amount": _d(inv_agg["iva"]),
            "total": _d(inv_agg["total"]),
            "count": inv_agg["count"] or 0,
        },
        "cuatrimestres": cuatrimestres,
        "cuatrimestre_actual": current,
        "iva_descontable": {
            "label": "IVA descontable",
            "hint": "IVA de gastos empresa aún no marcado como descontado. No es cuatrimestral.",
            "disponible": _d(available["iva"]),
            "disponible_count": available["count"] or 0,
            "ya_descontado": _d(used["iva"]),
            "ya_descontado_count": used["count"] or 0,
            "items": items,
        },
        # Compat con UI anterior
        "sales": {
            "iva_generated": _d(sales_agg["iva"]),
            "net_value": _d(sales_agg["net"]),
            "total_value": _d(sales_agg["total"]),
            "count": sales_agg["count"] or 0,
        },
        "invoices": {
            "iva": _d(inv_agg["iva"]),
            "total": _d(inv_agg["total"]),
            "count": inv_agg["count"] or 0,
        },
    }
