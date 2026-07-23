from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import F

from apps.audit.services import log_audit_event
from apps.config import settings_service as cfg
from apps.inventory.models import (
    KardexEntry,
    KardexItemType,
    KardexMovement,
    KardexReason,
    Product,
    ProductColor,
)


def allow_negative_stock() -> bool:
    try:
        # default True = allow negative with warning (doc)
        return bool(cfg.get("inventory.allow_negative_stock", True))
    except Exception:
        return True


def resolve_product_for_sale_item(item) -> Product:
    """Map SaleItem → Product; prefer color+tipo (kit), then woo id, then generic."""
    from apps.sales.kit_types import normalize_kit_type

    qs = Product.objects.filter(active=True)
    if getattr(item, "woo_product_id", None):
        match = qs.filter(woo_product_id=item.woo_product_id).first()
        if match:
            return match
    tipo = normalize_kit_type(getattr(item, "tipo", "") or "")
    if tipo and item.color:
        match = qs.filter(color=item.color, tipo=tipo, is_generic=False).first()
        if match:
            return match
    if item.tipo:
        match = qs.filter(color=item.color, tipo__iexact=item.tipo, is_generic=False).first()
        if match:
            return match
    generic = qs.filter(color=item.color, is_generic=True).first()
    if generic:
        return generic
    # last resort create generic
    sku = f"GEN-{item.color}"
    product, _ = Product.objects.get_or_create(
        sku=sku,
        defaults={
            "name": f"Seeds {item.color.title()} (genérico)",
            "color": item.color if item.color in ProductColor.values else ProductColor.OTRO,
            "is_generic": True,
            "active": True,
            "stock": 0,
        },
    )
    return product


@transaction.atomic
def _apply_product_movement(
    *,
    product: Product,
    movement: str,
    quantity: Decimal,
    reason: str,
    ref_type: str = "",
    ref_id: str = "",
    notes: str = "",
    actor=None,
) -> KardexEntry:
    product = Product.objects.select_for_update().get(id=product.id)
    qty = Decimal(quantity)
    if movement == KardexMovement.OUT:
        delta = -abs(qty)
    elif movement == KardexMovement.IN:
        delta = abs(qty)
    else:  # ADJUST — quantity signed by caller
        delta = qty

    new_stock = product.stock + int(delta)
    if new_stock < 0 and not allow_negative_stock():
        raise ValueError(f"Stock insuficiente para {product.sku} (disponible {product.stock}).")

    product.stock = new_stock
    product.save(update_fields=["stock", "updated_at"])

    entry = KardexEntry.objects.create(
        item_type=KardexItemType.PRODUCT,
        product=product,
        movement=movement,
        quantity=delta,
        balance=Decimal(product.stock),
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id,
        notes=notes,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    log_audit_event(
        actor=actor,
        action=f"KARDEX_{movement}",
        entity="Product",
        entity_id=str(product.id),
        metadata={
            "sku": product.sku,
            "delta": str(delta),
            "balance": product.stock,
            "reason": reason,
            "ref": f"{ref_type}:{ref_id}",
        },
    )
    return entry


@transaction.atomic
def discount_stock_for_shipment(shipment, *, actor=None) -> list[KardexEntry]:
    """Idempotent OUT on ENVIADO. Called from logistics.mark_shipments_sent."""
    ref_id = str(shipment.id)
    existing = KardexEntry.objects.filter(
        reason=KardexReason.DISPATCH,
        movement=KardexMovement.OUT,
        ref_type="Shipment",
        ref_id=ref_id,
    ).exists()
    if existing:
        return list(
            KardexEntry.objects.filter(
                reason=KardexReason.DISPATCH, ref_type="Shipment", ref_id=ref_id
            )
        )

    entries: list[KardexEntry] = []
    sale = shipment.sale
    for item in sale.items.all():
        product = resolve_product_for_sale_item(item)
        entry = _apply_product_movement(
            product=product,
            movement=KardexMovement.OUT,
            quantity=Decimal(item.quantity),
            reason=KardexReason.DISPATCH,
            ref_type="Shipment",
            ref_id=ref_id,
            notes=f"Despacho {sale.external_id}",
            actor=actor,
        )
        entries.append(entry)
    return entries


@transaction.atomic
def reverse_stock_for_shipment(shipment, *, actor=None) -> list[KardexEntry]:
    """Compensating IN on refund (used by accounting later)."""
    ref_id = str(shipment.id)
    outs = KardexEntry.objects.filter(
        reason=KardexReason.DISPATCH,
        movement=KardexMovement.OUT,
        ref_type="Shipment",
        ref_id=ref_id,
    )
    # idempotent reverse
    if KardexEntry.objects.filter(
        reason=KardexReason.REFUND, ref_type="Shipment", ref_id=ref_id
    ).exists():
        return []

    entries = []
    for out in outs:
        if not out.product_id:
            continue
        entries.append(
            _apply_product_movement(
                product=out.product,
                movement=KardexMovement.IN,
                quantity=abs(out.quantity),
                reason=KardexReason.REFUND,
                ref_type="Shipment",
                ref_id=ref_id,
                notes="Reversa por reembolso",
                actor=actor,
            )
        )
    return entries


def create_manual_entry(
    *,
    product: Product | None = None,
    material=None,
    movement: str,
    quantity: Decimal,
    reason: str = KardexReason.MANUAL_ADJUST,
    notes: str = "",
    actor=None,
) -> KardexEntry:
    if product is not None:
        if movement == KardexMovement.ADJUST:
            return _apply_product_movement(
                product=product,
                movement=KardexMovement.ADJUST,
                quantity=Decimal(quantity),
                reason=reason,
                notes=notes,
                actor=actor,
            )
        return _apply_product_movement(
            product=product,
            movement=movement,
            quantity=Decimal(quantity),
            reason=reason if reason else KardexReason.PURCHASE,
            notes=notes,
            actor=actor,
        )
    if material is not None:
        return _apply_material_movement(
            material=material,
            movement=movement,
            quantity=Decimal(quantity),
            reason=reason if reason else KardexReason.PURCHASE,
            notes=notes,
            actor=actor,
        )
    raise ValueError("Debes indicar producto o material.")


@transaction.atomic
def _apply_material_movement(
    *,
    material,
    movement: str,
    quantity: Decimal,
    reason: str,
    notes: str = "",
    actor=None,
) -> KardexEntry:
    from apps.inventory.models import Material

    material = Material.objects.select_for_update().get(id=material.id)
    qty = Decimal(quantity)
    if movement == KardexMovement.OUT:
        delta = -abs(qty)
    elif movement == KardexMovement.IN:
        delta = abs(qty)
    else:
        delta = qty

    new_stock = Decimal(material.stock) + delta
    if new_stock < 0 and not allow_negative_stock():
        raise ValueError(f"Stock insuficiente para {material.sku} (disponible {material.stock}).")

    material.stock = new_stock
    material.save(update_fields=["stock", "updated_at"])

    entry = KardexEntry.objects.create(
        item_type=KardexItemType.MATERIAL,
        material=material,
        movement=movement,
        quantity=delta,
        balance=material.stock,
        reason=reason,
        notes=notes,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    log_audit_event(
        actor=actor,
        action=f"KARDEX_MATERIAL_{movement}",
        entity="Material",
        entity_id=str(material.id),
        metadata={
            "sku": material.sku,
            "delta": str(delta),
            "balance": str(material.stock),
            "reason": reason,
        },
    )
    return entry


def low_stock_products():
    return Product.objects.filter(active=True).filter(stock__lte=F("reorder_level"))


def low_stock_materials():
    from apps.inventory.models import Material

    return Material.objects.filter(active=True).filter(stock__lte=F("reorder_level"))
