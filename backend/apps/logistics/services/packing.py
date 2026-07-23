from __future__ import annotations

from collections import defaultdict
from typing import Any

from apps.logistics.models import Shipment, ShipmentStatus
from apps.sales.kit_types import kit_type_label


def _product_label(color: str, product_name: str, tipo: str) -> str:
    color_label = {"DORADO": "Dorado", "PLATEADO": "Plateado"}.get(color, color or "Producto")
    kit = kit_type_label(tipo)
    if kit and color_label:
        return f"{kit} · {color_label}"
    base = (product_name or "").strip() or color_label
    if product_name and color in {"DORADO", "PLATEADO"} and color_label.lower() not in product_name.lower():
        base = f"{product_name} · {color_label}"
    if kit:
        return f"{base} · {kit}"
    if tipo.strip():
        return f"{base} · {tipo.strip()}"
    return base


def packing_summary(*, sent: bool = False) -> dict[str, Any]:
    """
    Resume pedidos listos (o enviados) para empacar: totales + cajas por producto.
    """
    status = ShipmentStatus.ENVIADO if sent else ShipmentStatus.LISTO_PARA_ENVIAR
    qs = (
        Shipment.objects.select_related("sale")
        .prefetch_related("sale__items")
        .filter(status=status)
    )

    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    order_ids_by_key: dict[tuple[str, str, str], set] = defaultdict(set)
    total_units = 0
    order_count = qs.count()

    for shipment in qs:
        sale = shipment.sale
        for item in sale.items.all():
            if not item.quantity:
                continue
            color = item.color or ""
            tipo = item.tipo or ""
            name = item.product_name or ""
            key = (color, name, tipo)
            if key not in buckets:
                buckets[key] = {
                    "key": f"{color}|{name}|{tipo}",
                    "label": _product_label(color, name, tipo),
                    "color": color,
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
