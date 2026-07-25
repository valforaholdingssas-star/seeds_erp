from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce, TruncMonth

from apps.finance.models import (
    BankMovement,
    EfeBudget,
    EfeMonthClose,
    FinancialAccount,
    FinancialAccountKind,
    MovementStatus,
)
from apps.sales.models import ConsolidatedSale, SaleSource, SaleState


# Resultados derivados del P&L (no son cuentas del árbol; se calculan en vivo).
# Convención de signos: ventas/ingresos (+), costos/gastos desde banco (−).
# Margen bruto = Ventas + COGS
# EBITDA     = Ventas + COGS + Admin + Costos op. + Gastos  (sin D&A explícito)
# NIAT       = EBITDA + Ingreso/Recaudo  (resultado después de recaudo/otros; excluye pasivos)
COMPUTED_RESULTS: list[dict] = [
    {
        "code": "MB",
        "name": "MARGEN BRUTO",
        "full_label": "MB. MARGEN BRUTO",
        "kind": "RESULTADO",
        "order": 36,
        "insert_after_prefix": "3",
        "components": ["1", "3"],
        "formula": "Ventas netas (1) + COGS (3)",
    },
    {
        "code": "EBITDA",
        "name": "EBITDA",
        "full_label": "EBITDA. EBITDA",
        "kind": "RESULTADO",
        "order": 76,
        "insert_after_prefix": "7",
        "components": ["1", "3", "5", "6", "7"],
        "formula": "Margen bruto − Admin (5) − Costos op. (6) − Gastos (7)",
    },
    {
        "code": "NIAT",
        "name": "NIAT",
        "full_label": "NIAT. NIAT (resultado neto)",
        "kind": "RESULTADO",
        "order": 78,
        "insert_after_prefix": "EBITDA",
        "components": ["1", "3", "4", "5", "6", "7"],
        "formula": "EBITDA + Ingreso/Recaudo (4) · excluye pasivos interbancarios (8)",
    },
]


def sale_efe_code(sale: ConsolidatedSale, *, shipping: bool = False) -> str | None:
    """Map ConsolidatedSale → leaf EFE code. MRR via income_source heuristic."""
    if shipping:
        return "1.2"
    if sale.state == SaleState.REFUNDED:
        return "1.3"
    if sale.state != SaleState.ACTIVE:
        return None

    income = (sale.income_source or "").upper()
    is_mrr = "MRR" in income or "RECURREN" in income

    src = sale.source
    if src == SaleSource.FERIAS:
        return "1.1.3"
    if src == SaleSource.ECOMMERCE:
        return "1.1.2.1" if is_mrr else "1.1.1.1"
    if src == SaleSource.KOMMO:
        return "1.1.2.2" if is_mrr else "1.1.1.2"
    if "FERIA" in income:
        return "1.1.3"
    return "1.1.1.2"


def _month_key(dt) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _sum_components(
    matrix: dict[str, dict[str, Decimal]], codes: list[str], months: list[str]
) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {m: Decimal("0") for m in months}
    for code in codes:
        row = matrix.get(code)
        if not row:
            continue
        for m in months:
            out[m] += Decimal(row.get(m) or 0)
    return out


def _append_computed_lines(
    *,
    lines: list[dict],
    matrix: dict[str, dict[str, Decimal]],
    months: list[str],
) -> list[dict]:
    computed_rows: list[dict] = []
    for spec in COMPUTED_RESULTS:
        real_dec = _sum_components(matrix, spec["components"], months)
        matrix[spec["code"]] = real_dec
        computed_rows.append(
            {
                "code": spec["code"],
                "name": spec["name"],
                "full_label": spec["full_label"],
                "kind": spec["kind"],
                "is_leaf": True,
                "parent": None,
                "depth": 0,
                "order": spec["order"],
                "computed": True,
                "formula": spec["formula"],
                "components": spec["components"],
                "real": {m: str(real_dec[m]) for m in months},
                "budget": {m: "0" for m in months},
                "variance": {m: str(real_dec[m]) for m in months},
            }
        )

    # Insert after the last account whose code starts with the given prefix.
    out = list(lines)
    for row in computed_rows:
        spec = next(s for s in COMPUTED_RESULTS if s["code"] == row["code"])
        prefix = spec["insert_after_prefix"]
        insert_at = len(out)
        for i, line in enumerate(out):
            code = line["code"]
            if prefix in {"MB", "EBITDA", "NIAT"}:
                if code == prefix:
                    insert_at = i + 1
            elif code == prefix or code.startswith(f"{prefix}."):
                insert_at = i + 1
        out.insert(insert_at, row)
    return out


def build_efe(year: int) -> dict:
    accounts = list(
        FinancialAccount.objects.filter(active=True)
        .select_related("parent")
        .order_by("order", "code")
    )
    months = [f"{year:04d}-{m:02d}" for m in range(1, 13)]
    matrix: dict[str, dict[str, Decimal]] = {
        a.code: {m: Decimal("0") for m in months} for a in accounts
    }

    # Sales → EFE 1.x
    sales = (
        ConsolidatedSale.objects.filter(
            state__in=[SaleState.ACTIVE, SaleState.REFUNDED],
        )
        .annotate(sale_month=TruncMonth(Coalesce("closed_at", "created_at")))
        .filter(sale_month__year=year)
        .only(
            "id",
            "source",
            "state",
            "total_value",
            "amount_shipping",
            "income_source",
            "closed_at",
            "created_at",
        )
    )
    for sale in sales.iterator():
        month_dt = sale.closed_at or sale.created_at
        if not month_dt or month_dt.year != year:
            continue
        mk = _month_key(month_dt)
        products = Decimal(sale.total_value or 0) - Decimal(sale.amount_shipping or 0)
        ship = Decimal(sale.amount_shipping or 0)
        if sale.state == SaleState.REFUNDED:
            code = "1.3"
            if code in matrix:
                matrix[code][mk] += -abs(Decimal(sale.total_value or 0))
            continue
        code = sale_efe_code(sale)
        if code and code in matrix:
            matrix[code][mk] += products
        if ship and "1.2" in matrix:
            matrix["1.2"][mk] += ship

    # Bank movements classified → non-sales leaves
    movs = (
        BankMovement.objects.filter(
            date__year=year,
            status__in=[MovementStatus.CLASIFICADO, MovementStatus.CONCILIADO],
            financial_account__isnull=False,
            financial_account__is_leaf=True,
        )
        .exclude(financial_account__kind=FinancialAccountKind.VENTAS)
        .values("financial_account__code", "date__month")
        .annotate(total=Sum("value"))
    )
    for row in movs:
        code = row["financial_account__code"]
        mk = f"{year:04d}-{int(row['date__month']):02d}"
        if code in matrix:
            matrix[code][mk] += Decimal(row["total"] or 0)

    def roll(node: FinancialAccount):
        kids = [c for c in accounts if c.parent_id == node.id]
        if not kids:
            return
        for k in kids:
            roll(k)
        for m in months:
            matrix[node.code][m] = sum((matrix[k.code][m] for k in kids), Decimal("0"))

    roots = [a for a in accounts if a.parent_id is None]
    for r in roots:
        roll(r)

    budgets = {
        (b.financial_account.code, b.month): b.amount
        for b in EfeBudget.objects.filter(year=year).select_related("financial_account")
    }
    closed = {
        c.month: {
            "closed_at": c.closed_at.isoformat(),
            "unclassified_pct": str(c.unclassified_pct),
            "note": c.note,
        }
        for c in EfeMonthClose.objects.filter(year=year)
    }

    lines = []
    for a in accounts:
        real = {m: str(matrix[a.code][m]) for m in months}
        ppto = {}
        var = {}
        for i, m in enumerate(months, start=1):
            b = budgets.get((a.code, i), Decimal("0"))
            ppto[m] = str(b)
            var[m] = str(matrix[a.code][m] - b)
        lines.append(
            {
                "code": a.code,
                "name": a.name,
                "full_label": a.full_label,
                "kind": a.kind,
                "is_leaf": a.is_leaf,
                "parent": a.parent.code if a.parent_id else None,
                "depth": a.code.count("."),
                "order": a.order,
                "computed": False,
                "real": real,
                "budget": ppto,
                "variance": var,
            }
        )

    lines = _append_computed_lines(lines=lines, matrix=matrix, months=months)

    return {
        "year": year,
        "months": months,
        "lines": lines,
        "closed_months": closed,
        "computed": [
            {
                "code": s["code"],
                "name": s["name"],
                "formula": s["formula"],
                "components": s["components"],
            }
            for s in COMPUTED_RESULTS
        ],
    }


def efe_drilldown(*, code: str, year: int, month: int) -> dict:
    spec = next((s for s in COMPUTED_RESULTS if s["code"] == code), None)
    if spec:
        efe = build_efe(year)
        mk = f"{year:04d}-{month:02d}"
        line = next((l for l in efe["lines"] if l["code"] == code), None)
        components = []
        for c in spec["components"]:
            src = next((l for l in efe["lines"] if l["code"] == c), None)
            components.append(
                {
                    "code": c,
                    "name": src["name"] if src else c,
                    "value": src["real"].get(mk, "0") if src else "0",
                }
            )
        return {
            "code": code,
            "name": spec["name"],
            "year": year,
            "month": month,
            "computed": True,
            "formula": spec["formula"],
            "value": line["real"].get(mk, "0") if line else "0",
            "components": components,
            "sales": [],
            "movements": [],
        }

    account = FinancialAccount.objects.filter(code=code).first()
    if not account:
        raise ValueError(f"Cuenta EFE {code} no existe")

    sales_out = []
    if account.kind == FinancialAccountKind.VENTAS or code.startswith("1."):
        qs = ConsolidatedSale.objects.filter(
            state__in=[SaleState.ACTIVE, SaleState.REFUNDED],
        ).annotate(sale_day=Coalesce("closed_at", "created_at"))
        qs = qs.filter(sale_day__year=year, sale_day__month=month)
        for sale in qs.select_related("seller")[:500]:
            mapped = sale_efe_code(sale)
            ship_code = "1.2"
            if code == "1.3" and sale.state == SaleState.REFUNDED:
                sales_out.append(
                    {
                        "type": "sale",
                        "id": str(sale.id),
                        "external_id": sale.external_id,
                        "customer": sale.customer_name,
                        "source": sale.source,
                        "value": str(sale.total_value),
                        "date": (sale.closed_at or sale.created_at).date().isoformat(),
                    }
                )
            elif code == ship_code and Decimal(sale.amount_shipping or 0):
                sales_out.append(
                    {
                        "type": "sale_shipping",
                        "id": str(sale.id),
                        "external_id": sale.external_id,
                        "value": str(sale.amount_shipping),
                        "date": (sale.closed_at or sale.created_at).date().isoformat(),
                    }
                )
            elif mapped == code:
                products = Decimal(sale.total_value or 0) - Decimal(sale.amount_shipping or 0)
                sales_out.append(
                    {
                        "type": "sale",
                        "id": str(sale.id),
                        "external_id": sale.external_id,
                        "customer": sale.customer_name,
                        "source": sale.source,
                        "value": str(products),
                        "date": (sale.closed_at or sale.created_at).date().isoformat(),
                    }
                )

    movs = (
        BankMovement.objects.filter(
            financial_account=account,
            date__year=year,
            date__month=month,
        )
        .select_related("bank")
        .order_by("date")[:500]
    )
    movements = [
        {
            "type": "movement",
            "id": str(m.id),
            "bank": m.bank.name,
            "date": m.date.isoformat(),
            "value": str(m.value),
            "concept": m.concept,
            "item": m.item,
            "is_interbank": m.is_interbank,
        }
        for m in movs
    ]
    return {
        "code": code,
        "name": account.name,
        "year": year,
        "month": month,
        "sales": sales_out,
        "movements": movements,
    }
