from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.audit.services import log_audit_event
from apps.config import settings_service as cfg
from apps.sales.models import (
    VALID_CONSOLIDATION_STATUSES,
    WITHDRAW_STATUSES,
    ConsolidatedSale,
    FulfillmentType,
    ProductPackRule,
    SaleColor,
    SaleItem,
    SaleSource,
    SaleState,
    SourceSaleBase,
)
from apps.sellers.services import resolve_vendedor
from apps.sales.services.payment_methods import resolve_payment_method
from apps.sales.services.fulfillment import normalize_fulfillment_type
from apps.sales.kit_types import infer_kit_type_from_name, normalize_kit_type


def get_iva_rate() -> Decimal:
    try:
        rate = cfg.get("business.iva_rate", Decimal("19"))
        return Decimal(str(rate))
    except Exception:
        return Decimal("19")


def calc_fiscal(total_value: Decimal, guide_cost: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """
    Base gravable = lo que el cliente pagó por producto:
      total_value − costo real de la guía Envia (no el flete cobrado al cliente).

    IVA_GENERADO = max(0, base − base/1.19)
    VALOR_AL_NETO = total_value − IVA_generado
    amount_products = base
    """
    total = Decimal(total_value or 0)
    shipping = Decimal(guide_cost or 0)
    taxable = total - shipping
    if taxable < 0:
        taxable = Decimal("0")
    rate = get_iva_rate()
    divisor = Decimal("1") + (rate / Decimal("100"))
    iva = max(Decimal("0"), taxable - (taxable / divisor))
    iva = iva.quantize(Decimal("0.01"))
    products = taxable.quantize(Decimal("0.01"))
    net = (total - iva).quantize(Decimal("0.01"))
    return products, iva, net


def guide_cost_for_sale(sale: ConsolidatedSale) -> Decimal:
    """Costo Envia de la guía; 0 si aún no hay guía / no aplica."""
    try:
        shipment = sale.shipment
    except Exception:
        return Decimal("0")
    if shipment is None or shipment.shipping_cost is None:
        return Decimal("0")
    return Decimal(shipment.shipping_cost)


def pack_multiplier(woo_product_id: str | None, product_name: str = "") -> int:
    if woo_product_id:
        rule = ProductPackRule.objects.filter(
            active=True, woo_product_id=str(woo_product_id)
        ).first()
        if rule:
            return int(rule.multiplier)
    name = (product_name or "").lower()
    if "3 kits" in name:
        return 3
    for rule in ProductPackRule.objects.filter(active=True).exclude(name_contains=""):
        if rule.name_contains.lower() in name:
            return int(rule.multiplier)
    return 1


def items_from_qtys(
    qty_dorados: int,
    qty_plateados: int,
    tipo_dorados: str = "",
    tipo_plateados: str = "",
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if qty_dorados:
        items.append(
            {
                "color": SaleColor.DORADO,
                "tipo": normalize_kit_type(tipo_dorados),
                "quantity": int(qty_dorados),
            }
        )
    if qty_plateados:
        items.append(
            {
                "color": SaleColor.PLATEADO,
                "tipo": normalize_kit_type(tipo_plateados),
                "quantity": int(qty_plateados),
            }
        )
    return items


def parse_woo_line_items(line_items: list[dict] | None) -> tuple[list[dict[str, Any]], int, int]:
    """Port of n8n Dorados/Plateados logic. Color from meta_data key=pa_color."""
    items: list[dict[str, Any]] = []
    qty_d = 0
    qty_p = 0
    for item in line_items or []:
        qty = int(item.get("quantity") or 0)
        product_id = str(item.get("product_id") or item.get("id") or "")
        name = str(item.get("name") or "")
        mult = pack_multiplier(product_id, name)
        unidades = qty * mult
        color_raw = ""
        for meta in item.get("meta_data") or []:
            if str(meta.get("key") or "").lower() == "pa_color":
                color_raw = str(meta.get("value") or "").lower()
                break
        if "dorado" in color_raw:
            color = SaleColor.DORADO
            qty_d += unidades
        elif "plateado" in color_raw:
            color = SaleColor.PLATEADO
            qty_p += unidades
        else:
            # default dorado if color missing but has qty
            color = SaleColor.DORADO
            qty_d += unidades
        items.append(
            {
                "color": color,
                "tipo": infer_kit_type_from_name(name),
                "quantity": unidades,
                "woo_product_id": product_id,
                "product_name": name,
            }
        )
    return items, qty_d, qty_p


def extract_woo_id_number(meta_data: list[dict] | None, meta_key: str | None = None) -> str:
    """Cédula by key — never by fixed index."""
    key = meta_key or cfg.get("woocommerce.id_meta_key", "billing_cedula") or "billing_cedula"
    for meta in meta_data or []:
        if str(meta.get("key") or "") == key:
            return str(meta.get("value") or "")
    # common fallbacks
    for candidate in ("billing_cedula", "_billing_cedula", "cedula", "CC"):
        for meta in meta_data or []:
            if str(meta.get("key") or "") == candidate:
                return str(meta.get("value") or "")
    return ""


def parse_shopify_line_items(line_items: list[dict] | None) -> tuple[list[dict[str, Any]], int, int]:
    """
    Dorados/Plateados from Shopify line items.
    Color from variant_title / title / properties (dorado|plateado).
    Pack multiplier reuses ProductPackRule (product_id or name_contains).
    """
    items: list[dict[str, Any]] = []
    qty_d = 0
    qty_p = 0
    for item in line_items or []:
        qty = int(item.get("quantity") or 0)
        product_id = str(item.get("product_id") or item.get("variant_id") or "")
        name = str(item.get("name") or item.get("title") or "")
        variant_title = str(item.get("variant_title") or "")
        mult = pack_multiplier(product_id, name)
        unidades = qty * mult

        color_raw = f"{variant_title} {name}".lower()
        for prop in item.get("properties") or []:
            pname = str(prop.get("name") or "").lower()
            pval = str(prop.get("value") or "").lower()
            if "color" in pname or "colour" in pname or pname in {"pa_color", "option1"}:
                color_raw = f"{color_raw} {pval}"
            else:
                color_raw = f"{color_raw} {pname} {pval}"

        if "plateado" in color_raw or "silver" in color_raw:
            color = SaleColor.PLATEADO
            qty_p += unidades
        elif "dorado" in color_raw or "gold" in color_raw:
            color = SaleColor.DORADO
            qty_d += unidades
        else:
            color = SaleColor.DORADO
            qty_d += unidades

        items.append(
            {
                "color": color,
                "tipo": infer_kit_type_from_name(name),
                "quantity": unidades,
                "woo_product_id": product_id,
                "product_name": name,
            }
        )
    return items, qty_d, qty_p


def extract_shopify_id_number(
    note_attributes: list[dict] | None = None,
    *,
    note: str = "",
    metafields: list[dict] | None = None,
    attr_name: str | None = None,
) -> str:
    """Cédula from note_attributes / metafields — never by fixed index."""
    key = (
        attr_name
        or cfg.get("shopify.id_note_attribute", "cedula")
        or "cedula"
    )
    key_l = str(key).lower()
    candidates = [key_l, "cedula", "cc", "documento", "document", "billing_cedula", "id_number"]

    for attr in note_attributes or []:
        name = str(attr.get("name") or attr.get("key") or "").lower()
        if name in candidates or name == key_l:
            val = str(attr.get("value") or "").strip()
            if val:
                return val

    for meta in metafields or []:
        mkey = str(meta.get("key") or "").lower()
        if mkey in candidates or mkey == key_l:
            val = str(meta.get("value") or "").strip()
            if val:
                return val

    # Last resort: "cedula: 123" in order note
    note_l = (note or "").lower()
    for token in ("cedula", "cc", "documento"):
        if token in note_l:
            for part in (note or "").replace("\n", " ").split():
                digits = "".join(ch for ch in part if ch.isdigit())
                if len(digits) >= 6:
                    return digits
    return ""


@transaction.atomic
def promote_to_consolidated(
    source_sale: SourceSaleBase,
    *,
    source: str,
    items: list[dict[str, Any]] | None = None,
    actor=None,
) -> ConsolidatedSale | None:
    if (source_sale.status or "").lower() not in VALID_CONSOLIDATION_STATUSES:
        return None

    seller = None
    if source == SaleSource.ECOMMERCE:
        seller = resolve_vendedor("ECOMMERCE", create_if_missing=True, actor=actor)
    elif source == SaleSource.SHOPIFY:
        seller = resolve_vendedor("SHOPIFY", create_if_missing=True, actor=actor)
    elif source == SaleSource.FERIAS:
        seller = resolve_vendedor(
            source_sale.commercial_raw or "FERIAS",
            create_if_missing=True,
            actor=actor,
        )
    else:
        seller = resolve_vendedor(
            source_sale.commercial_raw or "",
            create_if_missing=True,
            actor=actor,
        )

    products, iva, net = calc_fiscal(source_sale.total_value, Decimal("0"))

    payment_method = getattr(source_sale, "payment_method", None)
    if payment_method is None:
        payment_method = resolve_payment_method(source_sale.payment_account, actor=actor)
    payment_account = payment_method.name if payment_method else (source_sale.payment_account or "")

    sale, _created = ConsolidatedSale.objects.update_or_create(
        source=source,
        external_id=str(source_sale.external_id),
        defaults={
            "seller": seller,
            "customer_name": source_sale.customer_name,
            "email": source_sale.email,
            "phone": source_sale.phone,
            "id_number": source_sale.id_number,
            "address_raw": source_sale.address_raw,
            "city_raw": source_sale.city_raw,
            "state_raw": source_sale.state_raw,
            "amount_products": products,
            "amount_shipping": source_sale.amount_shipping,
            "total_value": source_sale.total_value,
            "iva_generated": iva,
            "net_value": net,
            "payment_account": payment_account,
            "payment_method": payment_method,
            "income_source": source_sale.income_source,
            "status": source_sale.status,
            "state": SaleState.ACTIVE,
            "deal_name": source_sale.deal_name,
            "stage": source_sale.stage,
            "closed_at": source_sale.closed_at,
            "symptoms": source_sale.symptoms,
            "order_notes": source_sale.order_notes,
            "age": source_sale.age,
            "requires_shipping": source_sale.requires_shipping,
            "fulfillment_type": normalize_fulfillment_type(
                getattr(source_sale, "fulfillment_type", None),
                requires_shipping=source_sale.requires_shipping,
            ),
            "withdrawn_reason": "",
        },
    )

    if payment_method and (
        source_sale.payment_method_id != payment_method.id
        or source_sale.payment_account != payment_account
    ):
        source_sale.payment_method = payment_method
        source_sale.payment_account = payment_account
        source_sale.save(update_fields=["payment_method", "payment_account", "updated_at"])

    line_items = items
    if line_items is None:
        line_items = items_from_qtys(
            source_sale.qty_dorados,
            source_sale.qty_plateados,
            source_sale.tipo_dorados,
            source_sale.tipo_plateados,
        )

    sale.items.all().delete()
    for item in line_items:
        if not item.get("quantity"):
            continue
        SaleItem.objects.create(
            sale=sale,
            color=item["color"],
            tipo=normalize_kit_type(item.get("tipo") or ""),
            quantity=int(item["quantity"]),
            woo_product_id=item.get("woo_product_id") or "",
            product_name=item.get("product_name") or "",
        )

    source_sale.consolidated_sale = sale
    source_sale.save(update_fields=["consolidated_sale", "updated_at"])

    log_audit_event(
        actor=actor,
        action="SALE_CONSOLIDATED",
        entity="ConsolidatedSale",
        entity_id=str(sale.id),
        metadata={"source": source, "external_id": sale.external_id},
    )
    return sale


@transaction.atomic
def withdraw_from_consolidated(
    sale: ConsolidatedSale,
    *,
    reason: str = "",
    state: str = SaleState.WITHDRAWN,
    actor=None,
    purge: bool = False,
) -> ConsolidatedSale | None:
    """
    Retira una venta del consolidado activo.
    - purge=False: marca WITHDRAWN y borra envíos/facturas pendientes.
    - purge=True: elimina la venta y lo relacionado (envío, factura, ítems).
    """
    if purge:
        purge_consolidated_sale(sale, reason=reason, actor=actor)
        return None

    _cleanup_sale_operations(sale, actor=actor)
    sale.state = state
    sale.withdrawn_reason = reason
    sale.save(update_fields=["state", "withdrawn_reason", "updated_at"])
    log_audit_event(
        actor=actor,
        action="SALE_WITHDRAWN",
        entity="ConsolidatedSale",
        entity_id=str(sale.id),
        metadata={"reason": reason, "state": state},
    )
    return sale


def _cleanup_sale_operations(sale: ConsolidatedSale, *, actor=None) -> None:
    """Quita envíos y facturas no emitidas asociadas a la venta."""
    from apps.accounting.models import Invoice, InvoiceStatus
    from apps.logistics.models import Shipment

    for shipment in Shipment.objects.filter(sale=sale):
        sid = str(shipment.id)
        shipment.delete()
        log_audit_event(
            actor=actor,
            action="SHIPMENT_REMOVED_ON_WITHDRAW",
            entity="Shipment",
            entity_id=sid,
            metadata={"sale": sale.external_id},
        )

    pending = Invoice.objects.filter(sale=sale).exclude(
        status__in=[InvoiceStatus.GENERADA]
    )
    for invoice in pending:
        iid = str(invoice.id)
        invoice.delete()
        log_audit_event(
            actor=actor,
            action="INVOICE_REMOVED_ON_WITHDRAW",
            entity="Invoice",
            entity_id=iid,
            metadata={"sale": sale.external_id},
        )


def purge_consolidated_sale(
    sale: ConsolidatedSale,
    *,
    reason: str = "",
    actor=None,
) -> None:
    """Hard-delete: venta + envío + factura/reembolsos locales + ítems."""
    from apps.accounting.models import Invoice, Refund
    from apps.logistics.models import Shipment

    sale_id = str(sale.id)
    external_id = sale.external_id

    Refund.objects.filter(sale=sale).delete()
    Invoice.objects.filter(sale=sale).delete()
    Shipment.objects.filter(sale=sale).delete()
    sale.delete()

    log_audit_event(
        actor=actor,
        action="SALE_PURGED",
        entity="ConsolidatedSale",
        entity_id=sale_id,
        metadata={"reason": reason, "external_id": external_id},
    )


def apply_status_transition(
    source_sale: SourceSaleBase,
    *,
    source: str,
    new_status: str,
    items: list[dict[str, Any]] | None = None,
    actor=None,
) -> ConsolidatedSale | None:
    source_sale.status = new_status
    source_sale.save(update_fields=["status", "updated_at"])
    status_l = (new_status or "").lower()
    if status_l in VALID_CONSOLIDATION_STATUSES:
        return promote_to_consolidated(source_sale, source=source, items=items, actor=actor)
    if status_l in WITHDRAW_STATUSES and source_sale.consolidated_sale_id:
        withdraw_from_consolidated(
            source_sale.consolidated_sale,
            reason=f"status:{new_status}",
            actor=actor,
        )
    return None


def recalculate_shipping(sale: ConsolidatedSale, shipping_cost: Decimal, actor=None) -> ConsolidatedSale:
    """
    Recalcula IVA / neto con el costo real de la guía Envia.
    No modifica amount_shipping (flete cobrado al cliente en la venta).
    """
    guide = Decimal(shipping_cost or 0)
    products, iva, net = calc_fiscal(sale.total_value, guide)
    sale.amount_products = products
    sale.iva_generated = iva
    sale.net_value = net
    sale.save(
        update_fields=[
            "amount_products",
            "iva_generated",
            "net_value",
            "updated_at",
        ]
    )
    log_audit_event(
        actor=actor,
        action="SALE_FISCAL_FROM_GUIDE",
        entity="ConsolidatedSale",
        entity_id=str(sale.id),
        metadata={"guide_cost": str(guide)},
    )
    return sale
