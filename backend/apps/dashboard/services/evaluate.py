from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone

from apps.dashboard.models import ControlIndicator, IndicatorSeverity, IndicatorSnapshot
from apps.dashboard.resolvers import resolve


def _effective_severity(indicator: ControlIndicator, value: Decimal) -> str:
    crit = indicator.crit_threshold
    warn = indicator.warn_threshold
    if crit is not None and value >= Decimal(crit):
        return IndicatorSeverity.CRITICAL
    if warn is not None and value >= Decimal(warn):
        return IndicatorSeverity.WARNING
    if indicator.severity == IndicatorSeverity.CRITICAL and value > 0:
        # keep base severity hint for zero-threshold criticals when value>0 already handled
        pass
    if value == 0:
        return IndicatorSeverity.INFO
    return indicator.severity


def evaluate_indicator(indicator: ControlIndicator) -> dict:
    cache_key = f"dash:ind:{indicator.key}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    raw = resolve(indicator.key)
    value = Decimal(raw.get("value") or 0)
    amount = raw.get("amount")
    amount_dec = Decimal(amount) if amount is not None else None
    severity = _effective_severity(indicator, value)
    snaps = list(
        indicator.snapshots.order_by("-captured_at")[:14].values_list("value", flat=True)
    )
    sparkline = [str(v) for v in reversed(snaps)]
    payload = {
        "id": str(indicator.id),
        "key": indicator.key,
        "label": indicator.label,
        "module": indicator.module,
        "description": indicator.description,
        "unit": indicator.unit,
        "base_severity": indicator.severity,
        "severity": severity,
        "warn_threshold": str(indicator.warn_threshold) if indicator.warn_threshold is not None else None,
        "crit_threshold": str(indicator.crit_threshold) if indicator.crit_threshold is not None else None,
        "target_url": indicator.target_url,
        "value": str(value),
        "amount": str(amount_dec) if amount_dec is not None else None,
        "meta": raw.get("meta") or {},
        "sparkline": sparkline,
        "order": indicator.order,
    }
    cache.set(cache_key, payload, 60)
    return payload


def dashboard_for_role(role: str, *, module: str | None = None) -> dict:
    qs = ControlIndicator.objects.filter(visible=True)
    if module:
        qs = qs.filter(module=module.upper())
    items = []
    for ind in qs:
        roles = ind.roles or []
        if roles and role not in roles and role != "ADMIN":
            continue
        items.append(evaluate_indicator(ind))
    critical = [i for i in items if i["severity"] == IndicatorSeverity.CRITICAL and Decimal(i["value"]) > 0]
    return {
        "as_of": timezone.now().isoformat(),
        "role": role,
        "critical": critical,
        "indicators": items,
    }


def capture_snapshots() -> int:
    n = 0
    for ind in ControlIndicator.objects.filter(visible=True):
        raw = resolve(ind.key)
        IndicatorSnapshot.objects.create(
            indicator=ind,
            value=Decimal(raw.get("value") or 0),
            amount=Decimal(raw["amount"]) if raw.get("amount") is not None else None,
        )
        cache.delete(f"dash:ind:{ind.key}")
        n += 1
    return n
