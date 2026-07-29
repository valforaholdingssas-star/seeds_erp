from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.sales.models import (
    FAILED_ECOMMERCE_STATUSES,
    EcommerceSale,
    FollowUpStatus,
    SaleSource,
    ShopifySale,
)

CHANNEL_MODELS = {
    SaleSource.ECOMMERCE: EcommerceSale,
    SaleSource.SHOPIFY: ShopifySale,
}


def _serialize_row(obj, *, channel: str) -> dict:
    contacted_by = getattr(obj, "contacted_by", None)
    return {
        "id": str(obj.id),
        "channel": channel,
        "external_id": obj.external_id,
        "status": obj.status,
        "deal_name": obj.deal_name or "",
        "closed_at": obj.closed_at.isoformat() if obj.closed_at else None,
        "total_value": str(obj.total_value),
        "amount_shipping": str(obj.amount_shipping),
        "payment_account": obj.payment_account or "",
        "customer_name": obj.customer_name or "",
        "email": obj.email or "",
        "phone": obj.phone or "",
        "id_number": obj.id_number or "",
        "address_raw": obj.address_raw or "",
        "city_raw": obj.city_raw or "",
        "state_raw": obj.state_raw or "",
        "qty_dorados": obj.qty_dorados,
        "qty_plateados": obj.qty_plateados,
        "order_notes": obj.order_notes or "",
        "follow_up_status": obj.follow_up_status,
        "follow_up_notes": obj.follow_up_notes or "",
        "contacted_at": obj.contacted_at.isoformat() if obj.contacted_at else None,
        "contacted_by": str(obj.contacted_by_id) if obj.contacted_by_id else None,
        "contacted_by_name": (
            (contacted_by.full_name or contacted_by.email) if contacted_by else ""
        ),
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _base_qs(model) -> QuerySet:
    return (
        model.objects.filter(consolidated_sale__isnull=True)
        .filter(status__in=FAILED_ECOMMERCE_STATUSES)
        .select_related("contacted_by")
    )


def list_failed_ecommerce(
    *,
    channel: str | None = None,
    follow_up_status: str | None = None,
    order_status: str | None = None,
    search: str | None = None,
    contacted: str | None = None,
) -> list[dict]:
    channels = [channel] if channel in CHANNEL_MODELS else list(CHANNEL_MODELS.keys())
    rows: list[dict] = []
    for ch in channels:
        model = CHANNEL_MODELS[ch]
        qs = _base_qs(model)
        if follow_up_status:
            qs = qs.filter(follow_up_status=follow_up_status)
        if order_status:
            qs = qs.filter(status=order_status)
        if contacted in {"1", "true", "yes"}:
            qs = qs.exclude(contacted_at__isnull=True)
        elif contacted in {"0", "false", "no"}:
            qs = qs.filter(contacted_at__isnull=True)
        if search:
            q = search.strip()
            qs = qs.filter(
                Q(customer_name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
                | Q(id_number__icontains=q)
                | Q(external_id__icontains=q)
                | Q(city_raw__icontains=q)
            )
        for obj in qs.order_by("-closed_at", "-created_at")[:500]:
            rows.append(_serialize_row(obj, channel=ch))
    rows.sort(key=lambda r: r.get("closed_at") or r.get("created_at") or "", reverse=True)
    return rows


def get_failed_ecommerce(*, channel: str, pk: str):
    model = CHANNEL_MODELS.get(channel)
    if not model:
        raise ValueError("Canal inválido (ECOMMERCE|SHOPIFY)")
    obj = (
        model.objects.filter(pk=pk, consolidated_sale__isnull=True)
        .select_related("contacted_by")
        .first()
    )
    if not obj:
        raise LookupError("Pedido no encontrado o ya consolidado")
    return obj


def update_follow_up(
    *,
    channel: str,
    pk: str,
    actor=None,
    follow_up_status: str | None = None,
    follow_up_notes: str | None = None,
    mark_contacted: bool = False,
) -> dict:
    obj = get_failed_ecommerce(channel=channel, pk=pk)
    fields: list[str] = ["updated_at"]

    if follow_up_status:
        if follow_up_status not in FollowUpStatus.values:
            raise ValueError("follow_up_status inválido")
        obj.follow_up_status = follow_up_status
        fields.append("follow_up_status")
        if follow_up_status == FollowUpStatus.CONTACTADO and not obj.contacted_at:
            mark_contacted = True
        if follow_up_status == FollowUpStatus.EN_SEGUIMIENTO and not obj.contacted_at:
            mark_contacted = True

    if follow_up_notes is not None:
        obj.follow_up_notes = follow_up_notes
        fields.append("follow_up_notes")

    if mark_contacted:
        obj.contacted_at = timezone.now()
        obj.contacted_by = actor
        fields.extend(["contacted_at", "contacted_by"])
        if obj.follow_up_status == FollowUpStatus.POR_CONTACTAR:
            obj.follow_up_status = FollowUpStatus.CONTACTADO
            fields.append("follow_up_status")

    obj.save(update_fields=list(dict.fromkeys(fields)))
    return _serialize_row(obj, channel=channel)
