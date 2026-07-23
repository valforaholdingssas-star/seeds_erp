from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.sales.models import FeriaSale, ManualSale, PaymentMethod, SaleSource
from apps.sales.services.fulfillment import apply_fulfillment
from apps.sales.services.normalization import promote_to_consolidated
from apps.sales.services.payment_methods import resolve_payment_method


def _resolve_payment_fields(data: dict, *, actor=None) -> tuple[str, PaymentMethod | None]:
    pm = None
    pm_id = data.get("payment_method")
    if pm_id:
        pm = PaymentMethod.objects.filter(id=pm_id, active=True).first()
    if pm is None:
        pm = resolve_payment_method(data.get("payment_account") or "", actor=actor)
    if pm:
        return pm.name, pm
    return (data.get("payment_account") or "").strip(), None


def _base_defaults(data: dict, *, income_source: str, commercial_raw: str, actor=None) -> dict:
    data = apply_fulfillment(dict(data))
    account, method = _resolve_payment_fields(data, actor=actor)
    return {
        "deal_name": data.get("deal_name") or data.get("customer_name") or "",
        "closed_at": data.get("closed_at") or timezone.now(),
        "total_value": Decimal(str(data.get("total_value") or 0)),
        "amount_shipping": Decimal(str(data.get("amount_shipping") or 0)),
        "payment_account": account,
        "payment_method": method,
        "income_source": income_source,
        "status": data.get("status") or "processing",
        "stage": data.get("stage") or "Cierre ganado",
        "commercial_raw": commercial_raw,
        "customer_name": data.get("customer_name") or "",
        "email": data.get("email") or "",
        "phone": data.get("phone") or "",
        "id_number": data.get("id_number") or "",
        "address_raw": data.get("address_raw") or "",
        "city_raw": data.get("city_raw") or "",
        "state_raw": data.get("state_raw") or "",
        "qty_dorados": int(data.get("qty_dorados") or 0),
        "qty_plateados": int(data.get("qty_plateados") or 0),
        "tipo_dorados": data.get("tipo_dorados") or "",
        "tipo_plateados": data.get("tipo_plateados") or "",
        "symptoms": data.get("symptoms") or "",
        "order_notes": data.get("order_notes") or "",
        "age": data.get("age") or "",
        "requires_shipping": bool(data.get("requires_shipping", True)),
        "fulfillment_type": data.get("fulfillment_type"),
        "extra": data.get("extra") or {},
    }


@transaction.atomic
def create_feria_sale(data: dict, *, actor=None):
    external_id = data.get("external_id") or f"FERIA-{uuid.uuid4().hex[:10].upper()}"
    sale = FeriaSale.objects.create(
        external_id=external_id,
        **_base_defaults(
            data,
            income_source="FERIAS",
            commercial_raw=data.get("commercial_raw") or "FERIAS",
            actor=actor,
        ),
    )
    consolidated = promote_to_consolidated(sale, source=SaleSource.FERIAS, actor=actor)
    return sale, consolidated


@transaction.atomic
def create_manual_sale(data: dict, *, actor=None):
    external_id = data.get("external_id") or f"MANUAL-{uuid.uuid4().hex[:10].upper()}"
    commercial = data.get("commercial_raw") or ""
    if not commercial:
        raise ValueError("Debes indicar el vendedor (commercial_raw) para ventas manuales.")
    sale = ManualSale.objects.create(
        external_id=external_id,
        **_base_defaults(data, income_source="MANUAL", commercial_raw=commercial, actor=actor),
    )
    consolidated = promote_to_consolidated(sale, source=SaleSource.MANUAL, actor=actor)
    return sale, consolidated
