# Seeds ERP — 03 · Módulo de Inventario

> Requiere `00_ARQUITECTURA`, `01_VENTAS` (SaleItem), `02_LOGISTICA` (evento "pedido enviado").
> App: `apps/inventory`. Submódulos: **Productos**, **Materiales**, **Kardex**.

Objetivo de esta fase: registrar los productos, y que el inventario **se descuente automáticamente por cada pedido enviado**, según tipo de producto y cantidad. Materiales y kardex se modelan para crecer (producción/insumos) después.

---

## 1. Modelos

```python
class Product(BaseModel):
    sku            = CharField(unique=True)
    name           = CharField()
    color          = CharField(choices=[('DORADO','Dorado'),('PLATEADO','Plateado'),('OTRO','Otro')], blank=True)
    tipo           = CharField(blank=True)          # "tipo dorados/plateados"
    woo_product_id = CharField(blank=True, db_index=True)  # enlaza con WooCommerce line_items
    active         = BooleanField(default=True)
    stock          = IntegerField(default=0)         # existencia actual (derivable del kardex)
    reorder_level  = IntegerField(default=0)         # alerta de stock bajo

class ProductPackRule(BaseModel):          # multiplicadores de packs (ver 01_VENTAS §4.3)
    product        = FK(Product, null=True)
    woo_product_id = CharField(blank=True) # p.ej. 602
    name_contains  = CharField(blank=True) # fallback por nombre: "3 kits"
    multiplier     = IntegerField(default=1)  # 602 -> 3

class Material(BaseModel):                 # insumos (fase de crecimiento)
    sku, name, unit (u/g/ml...), stock (Decimal), reorder_level

class BOMLine(BaseModel):                  # opcional: receta producto->materiales
    product = FK(Product); material = FK(Material); qty_per_unit = Decimal()

class KardexEntry(BaseModel):              # libro de movimientos (auditable, inmutable)
    item_type   = CharField(choices=[('PRODUCT','Producto'),('MATERIAL','Material')])
    product     = FK(Product, null=True)
    material    = FK(Material, null=True)
    movement    = CharField(choices=[('IN','Entrada'),('OUT','Salida'),('ADJUST','Ajuste')])
    quantity    = Decimal()                # + entrada / - salida
    balance     = Decimal()                # saldo resultante (snapshot)
    reason      = CharField()              # 'DISPATCH','PURCHASE','MANUAL_ADJUST','PRODUCTION'
    ref_type    = CharField(blank=True)    # 'Shipment','ConsolidatedSale'...
    ref_id      = CharField(blank=True)    # id de la referencia
    created_by  = FK(users.User, null=True)
```

El **stock es derivable del kardex** (fuente de verdad = suma de movimientos). `Product.stock` es un cache/snapshot que se actualiza en cada movimiento dentro de una transacción.

---

## 2. Descuento por pedido enviado (regla central)

Disparador: cuando un `Shipment` pasa a `ENVIADO` (en Despachos, `02 §6`).

Servicio `discount_stock_for_shipment(shipment)`:
1. En una **transacción atómica** (`select_for_update` sobre los productos afectados).
2. Por cada `SaleItem` de la venta asociada: `product`, `quantity` (unidades reales, ya con multiplicador aplicado en ventas).
3. Crear `KardexEntry(OUT, -quantity, reason='DISPATCH', ref=Shipment)` y actualizar `Product.stock`.
4. Idempotencia: no descontar dos veces el mismo shipment (chequear que no exista ya un kardex `OUT` con `ref_id=shipment.id`).
5. Si un producto no está mapeado (venta trae color/tipo sin `Product`): registrar movimiento en un producto "genérico dorado/plateado" o marcar para revisión (no fallar el despacho, pero sí alertar).
6. Permitir stock negativo con warning (el negocio decide si bloquear); por defecto **no bloquea** el envío, pero alerta.

---

## 3. Entradas de inventario
- Entrada manual (compra/producción): formulario → `KardexEntry(IN)`.
- Ajustes: `KardexEntry(ADJUST)` con motivo obligatorio y auditoría.
- (Fase 2) Consumo de materiales por producción vía BOM.

---

## 4. Pantallas
- **Productos:** tabla con stock actual, filtro por todas las columnas, edición masiva, alerta de `stock <= reorder_level`.
- **Materiales:** ídem.
- **Kardex:** vista de movimientos (inmutable), filtrable por producto/material, fecha, motivo, referencia. Exportable.

## 5. API (borrador)
```
GET/POST/PATCH /api/v1/inventory/products/
GET/POST/PATCH /api/v1/inventory/materials/
GET  /api/v1/inventory/kardex/?product=&from=&to=&reason=
POST /api/v1/inventory/entries/         # entradas/ajustes manuales
GET  /api/v1/inventory/alerts/          # stock bajo
```

## 6. Casos límite
| Caso | Manejo |
|---|---|
| Doble marca de "enviado" | Idempotencia por `ref_id` en kardex. |
| Venta sin producto mapeado | Producto genérico + alerta; no bloquea despacho. |
| Stock insuficiente | Permite negativo + warning (configurable a bloqueo). |
| Reversa de envío / reembolso | `KardexEntry(IN)` compensatorio al reembolsar (ver `04`). |
| Multiplicador de pack | Ya aplicado en ventas; inventario descuenta unidades reales. |
