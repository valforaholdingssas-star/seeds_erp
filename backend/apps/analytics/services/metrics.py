from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from apps.config import settings_service as cfg
from apps.sales.models import ConsolidatedSale, SaleState


WEEKDAY_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _aware_range(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(date_to, time.max), tz)
    return start, end


def _base_qs(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    source: str | None = None,
    seller: str | None = None,
    city: str | None = None,
):
    qs = ConsolidatedSale.objects.filter(state=SaleState.ACTIVE)
    if source:
        qs = qs.filter(source=source)
    if seller:
        qs = qs.filter(seller_id=seller)
    if city:
        qs = qs.filter(city_raw__icontains=city)
    if date_from and date_to:
        start, end = _aware_range(date_from, date_to)
        qs = qs.filter(created_at__gte=start, created_at__lte=end)
    elif date_from:
        start, _ = _aware_range(date_from, date_from)
        qs = qs.filter(created_at__gte=start)
    elif date_to:
        _, end = _aware_range(date_to, date_to)
        qs = qs.filter(created_at__lte=end)
    return qs


def _money(value) -> str:
    return str(Decimal(value or 0).quantize(Decimal("0.01")))


def _pct(current: Decimal, previous: Decimal) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return float(((current - previous) / previous * 100).quantize(Decimal("0.01")))


def _goal_month(*, seller: str | None = None) -> Decimal:
    if seller:
        try:
            from apps.sellers.models import Vendedor

            vendor = Vendedor.objects.filter(id=seller).only("monthly_goal").first()
            if vendor and vendor.monthly_goal is not None:
                return Decimal(vendor.monthly_goal)
        except Exception:
            pass
    try:
        return Decimal(str(cfg.get("business.sales_goal_month", "50000000") or "50000000"))
    except Exception:
        return Decimal("50000000")


def default_period() -> tuple[date, date]:
    today = timezone.localdate()
    return today.replace(day=1), today


def sales_summary(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    source: str | None = None,
    seller: str | None = None,
    city: str | None = None,
    compare: bool = True,
) -> dict[str, Any]:
    if not date_from or not date_to:
        date_from, date_to = default_period()

    qs = _base_qs(
        date_from=date_from,
        date_to=date_to,
        source=source,
        seller=seller,
        city=city,
    )
    agg = qs.aggregate(total=Sum("total_value"), iva=Sum("iva_generated"), orders=Count("id"))
    total = Decimal(agg["total"] or 0)
    orders = int(agg["orders"] or 0)

    days = max(1, (date_to - date_from).days + 1)
    # For monthly goal prorate by days in calendar month of date_to
    month_days = monthrange(date_to.year, date_to.month)[1]
    goal = _goal_month(seller=seller)
    # If range spans full month-ish use full goal else prorate
    if date_from.day == 1 and date_to.month == date_from.month:
        period_goal = (goal * Decimal(days) / Decimal(month_days)).quantize(Decimal("0.01"))
    else:
        period_goal = (goal * Decimal(days) / Decimal(30)).quantize(Decimal("0.01"))

    performance = float((total / period_goal * 100).quantize(Decimal("0.01"))) if period_goal else 0.0
    daily_expected = (period_goal / Decimal(days)).quantize(Decimal("0.01"))
    avg_daily = (total / Decimal(days)).quantize(Decimal("0.01"))
    # Projection: avg so far * remaining days in month (if current month) else avg * days
    today = timezone.localdate()
    if date_to.year == today.year and date_to.month == today.month:
        elapsed = max(1, (today - date_from).days + 1)
        remaining = max(0, month_days - today.day)
        run_rate = total / Decimal(elapsed)
        projection = (total + run_rate * Decimal(remaining)).quantize(Decimal("0.01"))
    else:
        projection = total

    prev = None
    if compare:
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=days - 1)
        prev_qs = _base_qs(
            date_from=prev_from,
            date_to=prev_to,
            source=source,
            seller=seller,
            city=city,
        )
        prev_agg = prev_qs.aggregate(total=Sum("total_value"), orders=Count("id"))
        prev_total = Decimal(prev_agg["total"] or 0)
        prev = {
            "from": prev_from.isoformat(),
            "to": prev_to.isoformat(),
            "total_value": _money(prev_total),
            "orders": int(prev_agg["orders"] or 0),
            "delta_pct": _pct(total, prev_total),
        }

    units = 0
    for sale in qs.prefetch_related("items"):
        units += sum(i.quantity for i in sale.items.all())

    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "filters": {"source": source, "seller": seller, "city": city},
        "kpis": {
            "goal": _money(period_goal),
            "goal_month": _money(goal),
            "sales": _money(total),
            "performance_pct": performance,
            "projection": _money(projection),
            "daily_expected": _money(daily_expected),
            "sales_to_date": _money(total),
            "avg_daily": _money(avg_daily),
            "vde_units": units,
            "orders": orders,
            "iva": _money(agg["iva"] or 0),
        },
        "previous": prev,
    }


def by_channel(**filters) -> dict[str, Any]:
    date_from = filters.pop("date_from", None)
    date_to = filters.pop("date_to", None)
    if not date_from or not date_to:
        date_from, date_to = default_period()
    qs = _base_qs(date_from=date_from, date_to=date_to, **filters)
    rows = (
        qs.values("source")
        .annotate(total=Sum("total_value"), orders=Count("id"))
        .order_by("-total")
    )
    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "series": [
            {"key": r["source"], "label": r["source"], "total": _money(r["total"]), "orders": r["orders"]}
            for r in rows
        ],
    }


def by_seller(**filters) -> dict[str, Any]:
    date_from = filters.pop("date_from", None)
    date_to = filters.pop("date_to", None)
    if not date_from or not date_to:
        date_from, date_to = default_period()
    qs = _base_qs(date_from=date_from, date_to=date_to, **filters)
    rows = (
        qs.values("seller__name")
        .annotate(total=Sum("total_value"), orders=Count("id"))
        .order_by("-total")
    )
    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "series": [
            {
                "key": r["seller__name"] or "Sin asignar",
                "label": r["seller__name"] or "Sin asignar",
                "total": _money(r["total"]),
                "orders": r["orders"],
            }
            for r in rows
        ],
    }


def by_city(**filters) -> dict[str, Any]:
    date_from = filters.pop("date_from", None)
    date_to = filters.pop("date_to", None)
    scope = filters.pop("scope", "month")
    if scope == "historic":
        date_from = date_to = None
        qs = _base_qs(**{k: v for k, v in filters.items() if k in {"source", "seller", "city"}})
    else:
        if not date_from or not date_to:
            date_from, date_to = default_period()
        qs = _base_qs(date_from=date_from, date_to=date_to, **filters)
    rows = (
        qs.values("city_raw")
        .annotate(total=Sum("total_value"), orders=Count("id"))
        .order_by("-total")[:15]
    )
    return {
        "scope": scope,
        "from": date_from.isoformat() if date_from else None,
        "to": date_to.isoformat() if date_to else None,
        "series": [
            {
                "key": r["city_raw"] or "Sin ciudad",
                "label": r["city_raw"] or "Sin ciudad",
                "total": _money(r["total"]),
                "orders": r["orders"],
            }
            for r in rows
        ],
    }


def timeseries(
    *,
    granularity: str = "day",
    date_from: date | None = None,
    date_to: date | None = None,
    source: str | None = None,
    seller: str | None = None,
    city: str | None = None,
) -> dict[str, Any]:
    if not date_from or not date_to:
        date_from, date_to = default_period()
    qs = _base_qs(
        date_from=date_from,
        date_to=date_to,
        source=source,
        seller=seller,
        city=city,
    )
    if granularity == "month":
        trunc = TruncMonth("created_at")
    else:
        trunc = TruncDate("created_at")
    rows = (
        qs.annotate(bucket=trunc)
        .values("bucket")
        .annotate(total=Sum("total_value"), orders=Count("id"))
        .order_by("bucket")
    )
    days = max(1, (date_to - date_from).days + 1)
    goal = _goal_month(seller=seller)
    daily_expected = float(goal / Decimal(30))
    points = []
    running = []
    for r in rows:
        bucket = r["bucket"]
        label = bucket.date().isoformat() if hasattr(bucket, "date") else str(bucket)[:10]
        total = float(r["total"] or 0)
        running.append(total)
        avg = sum(running) / len(running)
        points.append(
            {
                "date": label,
                "total": _money(r["total"]),
                "orders": r["orders"],
                "daily_expected": _money(daily_expected),
                "avg": _money(avg),
            }
        )
    return {
        "granularity": granularity,
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "points": points,
        "days_in_range": days,
    }


def weekday_bars(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    source: str | None = None,
    seller: str | None = None,
    city: str | None = None,
) -> dict[str, Any]:
    today = timezone.localdate()
    month_from = today.replace(day=1)
    month_to = today
    hist_from = today - timedelta(days=365)

    def _buckets(qs):
        counts = [0.0] * 7
        for sale in qs.only("created_at", "total_value"):
            # Monday=0
            idx = timezone.localtime(sale.created_at).weekday()
            counts[idx] += float(sale.total_value or 0)
        return [
            {"weekday": i, "label": WEEKDAY_LABELS[i], "total": _money(v)}
            for i, v in enumerate(counts)
        ]

    month_qs = _base_qs(
        date_from=month_from,
        date_to=month_to,
        source=source,
        seller=seller,
        city=city,
    )
    hist_qs = _base_qs(
        date_from=hist_from,
        date_to=today,
        source=source,
        seller=seller,
        city=city,
    )
    return {
        "month": _buckets(month_qs),
        "historic": _buckets(hist_qs),
        "from": (date_from or month_from).isoformat(),
        "to": (date_to or month_to).isoformat(),
    }


def year_comparison(
    *,
    source: str | None = None,
    seller: str | None = None,
    city: str | None = None,
) -> dict[str, Any]:
    today = timezone.localdate()
    year = today.year
    current = _base_qs(
        date_from=date(year, 1, 1),
        date_to=today,
        source=source,
        seller=seller,
        city=city,
    )
    previous = _base_qs(
        date_from=date(year - 1, 1, 1),
        date_to=date(year - 1, 12, 31),
        source=source,
        seller=seller,
        city=city,
    )

    def _by_month(qs):
        rows = (
            qs.annotate(bucket=TruncMonth("created_at"))
            .values("bucket")
            .annotate(total=Sum("total_value"))
            .order_by("bucket")
        )
        out = {i: 0.0 for i in range(1, 13)}
        for r in rows:
            m = r["bucket"].month if r["bucket"] else None
            if m:
                out[m] = float(r["total"] or 0)
        return out

    cur = _by_month(current)
    prev = _by_month(previous)
    return {
        "year": year,
        "previous_year": year - 1,
        "points": [
            {
                "month": m,
                "label": date(2000, m, 1).strftime("%b"),
                "current": _money(cur[m]),
                "previous": _money(prev[m]),
            }
            for m in range(1, 13)
        ],
    }
