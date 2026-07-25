from __future__ import annotations

from collections import defaultdict
from typing import Any

from apps.logistics.models import Shipment, ShipmentStatus
from apps.logistics.services.shipments import operational_shipments
from apps.sales.kit_types import kit_type_label, normalize_kit_type


def _product_label(color: str, tipo: str, product_name: str = "") -> str:
    color_label = {"DORADO": "Dorado", "PLATEADO": "Plateado"}.get(color, color or "Producto")
    kit = kit_type_label(tipo) or kit_type_label(product_name)
    if kit:
        return f"{kit} · {color_label}" if color_label else kit
    base = (product_name or "").strip() or color_label
    if tipo.strip() and tipo.strip() not in base:
        return f"{base} · {tipo.strip()}"
    return base


def packing_summary(*, sent: bool = False) -> dict[str, Any]:
    """
    Resume pedidos listos (o enviados) para empacar: totales + cajas por producto.
    Agrupa por tipo de kit normalizado + color (una sola caja por variante).
    """
    status = ShipmentStatus.ENVIADO if sent else ShipmentStatus.LISTO_PARA_ENVIAR
    qs = operational_shipments(
        Shipment.objects.select_related("sale")
        .prefetch_related("sale__items")
        .filter(status=status)
    )

    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    order_ids_by_key: dict[tuple[str, str], set] = defaultdict(set)
    total_units = 0
    order_count = qs.count()

    for shipment in qs:
        sale = shipment.sale
        for item in sale.items.all():
            if not item.quantity:
                continue
            color = (item.color or "").strip().upper() or "OTRO"
            name = (item.product_name or "").strip()
            tipo_raw = (item.tipo or "").strip()
            tipo = normalize_kit_type(tipo_raw) or normalize_kit_type(name) or tipo_raw or name or "OTRO"
            key = (tipo, color)
            if key not in buckets:
                buckets[key] = {
                    "key": f"{tipo}|{color}",
                    "label": _product_label(color, tipo, name),
                    "color": color if color != "OTRO" else "",
                    "tipo": tipo,
                    "product_name": name,
                    "units": 0,
                    "orders": 0,
                }
            buckets[key]["units"] += item.quantity
            order_ids_by_key[key].add(str(sale.id))
            total_units += item.quantity

    products = []
    for key, row in buckets.items():
        row["orders"] = len(order_ids_by_key[key])
        products.append(row)

    products.sort(key=lambda p: (-p["units"], p["label"]))

    by_color = {"DORADO": 0, "PLATEADO": 0, "OTRO": 0}
    for p in products:
        if p["color"] in by_color:
            by_color[p["color"]] += p["units"]
        else:
            by_color["OTRO"] += p["units"]

    return {
        "orders": order_count,
        "total_units": total_units,
        "by_color": by_color,
        "products": products,
    }
