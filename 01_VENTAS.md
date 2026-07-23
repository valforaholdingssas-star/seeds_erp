# Seeds ERP — 01 · Módulo de Ventas

> Requiere `00_ARQUITECTURA` (especialmente §7 Consolidado, §8 Ingesta recovery-first, §10 operaciones masivas).
> App: `apps/sales` + `apps/sellers`.

Este módulo consolida las ventas de **4 fuentes**: Ecommerce (WooCommerce), Kommo, Ferias y Manuales. Cada fuente escribe en su tabla de origen; un servicio de normalización promueve a `ConsolidatedSale`. Solo entran al consolidado las ventas `processing`/`completed`.

---

## 1. Modelos

### 1.1 Tablas de origen (una por canal — espejo de las hojas `N8N_*` / `VENTAS *`)

Un modelo abstracto `SourceSaleBase` con los campos crudos comunes, y una tabla concreta por canal para preservar trazabilidad del dato tal como llegó:

```python
class SourceSaleBase(BaseModel):
    external_id       = CharField(db_index=True)          # order_id / lead_id / form id
    raw_event         = FK(integrations.RawWebhookEvent, null=True)
    deal_name         = CharField(blank=True)             # "Nombre del negocio"
    closed_at         = DateTimeField(null=True)          # "Fecha de cierre"
    total_value       = Decimal()                          # "Valor"
    amount_shipping   = Decimal(default=0)                 # "TRASPORTE"
    payment_account   = CharField(blank=True)             # "Cuenta bancaria"
    income_source     = CharField()                        # E-COMMERCE / KOMMO / FERIAS / MANUAL
    status            = CharField()                        # processing/completed/pending/failed/cancelled
    stage             = CharField(blank=True)             # "Etapa del negocio"
    commercial_raw    = CharField(blank=True)             # texto del vendedor tal como llega
    customer_name     = CharField(blank=True)
    email             = EmailField(blank=True)
    phone             = CharField(blank=True)
    id_number         = CharField(blank=True)             # cédula "CC"
    address_raw       = CharField(blank=True)
    city_raw          = CharField(blank=True)
    state_raw         = CharField(blank=True)             # municipio/departamento
    qty_dorados       = IntegerField(default=0)
    qty_plateados     = IntegerField(default=0)
    tipo_dorados      = CharField(blank=True)
    tipo_plateados    = CharField(blank=True)
    symptoms          = CharField(blank=True)             # "Síntoma/s"
    order_notes       = TextField(blank=True)
    age               = CharField(blank=True)
    extra             = JSONField(default=dict)           # cualquier campo adicional del canal
    consolidated_sale = FK(ConsolidatedSale, null=True)   # link cuando se promueve
    class Meta: abstract = True

class EcommerceSale(SourceSaleBase):  ...   # hoja N8N_ECOMMERCE / VENTAS ECOMMERCE
class KommoSale(SourceSaleBase):      ...   # hoja N8N_KOMMO / VENTAS KOMMO
class FeriaSale(SourceSaleBase):      ...   # formulario ferias
class ManualSale(SourceSaleBase):     ...   # formulario manual
```

> Alternativa: una sola tabla `SourceSale` con `source` como campo. Se prefieren tablas separadas porque cada canal tiene campos y validaciones propias, igual que hay hojas separadas hoy. El agente puede elegir, pero debe mantener la clave natural `(source, external_id)`.

### 1.2 `ConsolidatedSale` (ver `00_ARQUITECTURA §7`)

```python
class ConsolidatedSale(BaseModel):
    source          = CharField(choices=Source)           # ECOMMERCE/KOMMO/FERIA/MANUAL
    external_id     = CharField()
    seller          = FK(sellers.Vendedor)                # "Comercial" resuelto a entidad
    customer        = FK(accounting.Customer, null=True)  # se enlaza al crear cliente
    # datos negocio
    customer_name   = CharField()
    email           = EmailField(blank=True)
    phone           = CharField(blank=True)
    id_number       = CharField(blank=True)
    address_raw     = CharField(blank=True)
    city_raw        = CharField(blank=True)
    state_raw       = CharField(blank=True)
    # dinero
    amount_products = Decimal()
    amount_shipping = Decimal(default=0)
    total_value     = Decimal()
    iva_generated   = Decimal(default=0)
    net_value       = Decimal(default=0)
    # operativos
    payment_account = CharField(blank=True)
    income_source   = CharField()
    status          = CharField()                          # processing/completed
    state           = CharField(choices=SaleState, default='ACTIVE')  # DRAFT/ACTIVE/WITHDRAWN/REFUNDED
    closed_at       = DateTimeField(null=True)
    symptoms        = CharField(blank=True)
    order_notes     = TextField(blank=True)
    class Meta:
        constraints = [UniqueConstraint(fields=['source','external_id'], name='uq_sale_source_extid')]
        indexes = [ ... por cada columna filtrable ... ]

class SaleItem(BaseModel):
    sale     = FK(ConsolidatedSale, related_name='items')
    product  = FK(inventory.Product, null=True)
    color    = CharField(choices=[('DORADO','Dorado'),('PLATEADO','Plateado')])
    tipo     = CharField(blank=True)
    quantity = IntegerField()   # unidades reales (con multiplicador de pack ya aplicado)
```

---

## 2. `sellers.Vendedor` (módulo Vendedores — parametrizable)

Requisito explícito: los vendedores se parametrizan; un vendedor es un objeto (p.ej. "VENDEDORA 1") que **puede** tener un `User` asociado **o no** (ECOMMERCE, FERIAS no son personas).

```python
class Vendedor(BaseModel):
    name        = CharField(unique=True)      # "VENDEDORA 1", "ECOMMERCE", "FERIAS", "RETENCIÓN 1"
    user        = FK(users.User, null=True, blank=True)   # opcional
    is_system   = BooleanField(default=False) # True para ECOMMERCE/FERIAS (no personas)
    active      = BooleanField(default=True)
    aliases     = JSONField(default=list)     # ["Marina","Maji","Lau"...] para mapear texto crudo
```

Valores reales observados en datos: `ECOMMERCE`, `VENDEDORA 1`, `RETENCIÓN 1`, `FERIAS`, `Marina`, `Maji`, `Lau`, `Dani`. El servicio de normalización resuelve `commercial_raw → Vendedor` por `name` o `aliases`; si no existe, crea un Vendedor "por revisar" y marca la venta para revisión (nunca se pierde la venta). Debe existir CRUD de Vendedores (solo ADMIN).

Asignación de vendedor por canal:
- **Ecommerce** → siempre Vendedor `ECOMMERCE` (system).
- **Kommo** → el que trae el lead (campo `Comercial` del custom field, ver §5).
- **Ferias** → Vendedor `FERIAS` (o el seleccionado en el formulario).
- **Manual** → el seleccionado en el formulario.

---

## 3. Servicio de normalización (origen → consolidado)

Función central `promote_to_consolidated(source_sale) -> ConsolidatedSale | None`:

1. Si `status ∉ {processing, completed}` → **no** promueve (queda en origen). Registra motivo.
2. Resuelve `seller` (via §2).
3. Calcula ítems `SaleItem` a partir de `qty_dorados/qty_plateados/tipo_*` (y del desglose de line items en Ecommerce, aplicando multiplicador de pack).
4. Calcula dinero: `amount_products`, `amount_shipping`, IVA/neto (fórmulas de `00 §7.5`).
5. Upsert por `(source, external_id)`. Si ya existe: actualiza (no duplica). Enlaza `source_sale.consolidated_sale`.
6. Emite `AuditLog(SALE_CONSOLIDATED)` y dispara señales para contabilidad (crear registro "factura por generar", ver `04`) e inventario si aplica.
7. Devuelve la venta consolidada.

Retirada: `withdraw_from_consolidated(sale, reason)` cambia `state` y descuenta de métricas (usado cuando una orden pasa a cancelled/failed/refunded).

---

## 4. Canal 1 · Ecommerce (WooCommerce)

### 4.1 Flujo actual (referencia)
WooCommerce → webhook → n8n (parseo JS + append) → Google Sheets `N8N_ECOMMERCE` → hoja `VENTAS ECOMMERCE` (transformación) → `CONSOLIDADO VENTAS`. Un segundo workflow (`WOOCOMMERCE ORDER UPDATE`) actualiza el estado por `Deal ID`.

### 4.2 Flujo nuevo en el ERP

**a) Alta de orden.** WooCommerce llama a `POST /api/v1/webhooks/woocommerce/order-created/`.
- Persistir `RawWebhookEvent` y responder 200 (recovery-first).
- Task de proceso: parsear payload → `EcommerceSale` (upsert por `order_id`) → si `status ∈ {processing,completed}` promover a consolidado.

**b) Parseo del payload** (campos confirmados del webhook real):
| Campo consolidado | Origen en payload WooCommerce |
|---|---|
| `external_id` | `body.id` |
| `status` | `body.status` |
| `closed_at` | `body.date_created` |
| `total_value` | `body.total` |
| `email` | `body.billing.email` |
| `customer_name` | `body.billing.first_name + last_name` |
| `phone` | `body.billing.phone` |
| `city_raw` | `body.billing.city` |
| `address_raw` | `body.billing.address_1 + ' - ' + address_2` |
| `id_number` (CC) | `body.meta_data[*]` con la key de cédula (hoy `meta_data[2].value`; **no** confiar en el índice: buscar por `key`) |
| `customer_id` | `body.customer_id` |
| ítems Dorados/Plateados | `body.line_items[*]` → ver 4.3 |

**c) Valores por defecto del canal:** `income_source='E-COMMERCE'`, `payment_account` según pasarela (Mercadopago por defecto en el flujo actual, pero preferible leer de `body.payment_method`), `stage='Cierre ganado'`, `seller=ECOMMERCE`.

### 4.3 Cálculo Dorados/Plateados (portar el Code node de n8n)

```
Para cada line_item:
  qty        = item.quantity
  multiplier = ProductPackRule.get(item.product_id) or (3 si name contiene "3 kits") or 1
  color      = item.meta_data[key='pa_color'].value.lower()   # 'dorado(s)'/'plateado(s)'
  unidades   = qty * multiplier
  acumular en dorados/plateados según color
```
`ProductPackRule` es parametrizable (hoy: `602 → 3`). Guardar el detalle por line item en `SaleItem`.

### 4.4 Actualización de estado (portar `WOOCOMMERCE ORDER UPDATE`)

WooCommerce llama a `POST /api/v1/webhooks/woocommerce/order-updated/` con `{id, status, billing...}`.
- Buscar `EcommerceSale` por `order_id`, actualizar `status`.
- Aplicar reglas de `00 §7.3`: promover si pasa a processing/completed; retirar del consolidado si pasa a cancelled/failed/refunded.

### 4.5 Actualización manual por rango de fechas (requisito nuevo)

Endpoint + pantalla: **selector de rango de fechas** que consulta la WooCommerce REST API (`GET /wp-json/wc/v3/orders?after=&before=&status=`) y reconcilia estados de todas las órdenes del rango contra el ERP. Útil para recuperar órdenes cuyo webhook se perdió, o corregir estados desincronizados. Se ejecuta como `BatchJob` secuencial (paginado, respetando rate limits de WooCommerce).

### 4.6 Plugin de WordPress propio (recomendado)

**Recomendación: sí, construir un plugin ligero compatible con WooCommerce.** Ventajas sobre el webhook nativo:
- Firma HMAC estable y reintentos del lado de WordPress si el ERP no responde 200 (cola local → no se pierden órdenes si el ERP está caído).
- Envío de un payload canónico y consistente (evita depender de `meta_data[índice]` frágil para la cédula: el plugin mapea explícitamente el campo cédula).
- Endpoint de *health* y de *resync* (reenvía órdenes de un rango).
- Manejo unificado de order.created y order.updated (status), con `dedupe_key`.

Especificación mínima del plugin:
- Hooks `woocommerce_new_order`, `woocommerce_order_status_changed`.
- POST a `SEEDS_ERP_URL` con header `X-Seeds-Signature: HMAC-SHA256(payload, secret)`.
- Reintentos con backoff + cola persistente (transient/tabla propia) hasta recibir 200.
- Pantalla de configuración (URL, secret, campo de cédula, activar/desactivar).

El ERP valida la firma y trata el payload igual que el webhook (mismo pipeline).

---

## 5. Canal 2 · Kommo

### 5.1 Flujo actual (referencia)
Comercial mueve el lead a una columna concreta → webhook → n8n:
1. Parsea el body (form-encoded): `leads[status][0][id]`, `status_id`, `pipeline_id`, `old_status_id`, `account[id]`, `account[subdomain]`.
2. `GET https://<sub>.kommo.com/api/v4/leads/{lead_id}?with=contacts` → datos del lead + custom fields.
3. `GET https://<sub>.kommo.com/api/v4/contacts/{first_contact_id}` → email, teléfono, cédula.
4. Escribe a `N8N_KOMMO` → hoja `VENTAS KOMMO` → consolidado. (Además dispara logística; ver `02`.)

### 5.2 Flujo nuevo en el ERP

Endpoint `POST /api/v1/webhooks/kommo/lead-status-changed/`:
- Persistir `RawWebhookEvent`, responder 200.
- Task: verificar que `status_id`/`pipeline_id` corresponden a la **columna de venta ganada** (parametrizable — no hardcodear el id). Si no, `IGNORED`.
- Llamar a Kommo API (lead + contacto) con el cliente OAuth2 de `integrations` (token long-lived, refresh automático).
- Construir `KommoSale` (upsert por `lead_id`) y promover a consolidado.

### 5.3 Mapeo de campos (confirmado del workflow)

Del **lead** (`custom_fields_values` por `field_name`):
| Consolidado | Campo Kommo |
|---|---|
| `external_id` | `lead.id` |
| `deal_name` | `lead.name` |
| `total_value` | `lead.price` |
| `seller` | custom field `Comercial` |
| `payment_account` | `Medio de pago` |
| `income_source` | `KOMMO` (fijo) |
| `city_raw` | `Ciudad` |
| `address_raw` | `Dirección entrega` / `Direccion entrega` |
| `id_number` | (del contacto) `Cédula de ciudadanía` |
| `qty_dorados` | `# Seeds Dorados` |
| `qty_plateados` | `# Seeds plateados` |
| `tipo_dorados` | `Tipo dorados` |
| `tipo_plateados` | `Tipo plateados` |
| `symptoms` | `Síntoma/s` |
| `order_notes` | `NOTAS DEL PEDIDO` |
| `age` | `Edad` |
| `closed_at` | `FECHA DE CIERRE` (epoch → fecha) |

Del **contacto** (`custom_fields_values` por `field_code`): `EMAIL` (primer valor), `PHONE` (primer valor). Cédula por `field_name='Cédula de ciudadanía'`.

Cálculos: `neto = valor/1.19`, `iva = valor − neto`, `transporte = 0` inicial. `status` inicial `processing` (así lo hace el flujo actual al entrar por la columna ganada).

### 5.4 Notas
- Extraer a `integrations` un cliente Kommo reutilizable (auth, base URL por subdominio, manejo de rate limits de Kommo).
- Guardar `pipeline_id`/`status_id` en `extra` para trazabilidad.

---

## 6. Canales 3 y 4 · Ferias y Manuales (formularios internos)

Requisito: reemplazar los Google Forms por **formularios dentro del ERP** que escriben directo a `FeriaSale` / `ManualSale` con los mismos campos del consolidado.

- **Ferias:** formulario con los campos del consolidado (cliente, contacto, dirección, ciudad/depto, cédula, productos+cantidades, valor, medio de pago). `income_source='FERIAS'`, `seller=FERIAS` (o el seleccionado). Al guardar: crea origen + promueve a consolidado.
- **Manuales:** idéntico, `income_source='MANUAL'`, vendedor seleccionable. Para ventas de canales alternativos.
- Ambos: validación fuerte de campos (dirección/ciudad requeridas si habrá envío), y opción de marcar "no requiere envío".

---

## 7. Importación masiva CSV / carga histórica

Requisito: poder cargar de forma masiva todo lo que hay en `SD VENTAS 2026`.

Dos caminos, ambos deseables:

**a) Importador CSV desde la UI** (módulo de consolidado):
- Subir CSV → mapeo de columnas (auto-detección + ajuste manual) → validación fila por fila → *dry-run* con reporte de errores/duplicados → confirmación → inserción.
- Idempotente por `(source, external_id)`: filas existentes se actualizan o se saltan (elección del usuario).
- Genera un `ImportJob` con resumen (creadas, actualizadas, rechazadas + motivo). Nada se inserta a medias: si una fila falla, se reporta pero no bloquea el resto.

**b) Carga histórica por script (seed) en el IDE** (recomendado para el arranque):
- Comando de management `python manage.py import_sd_ventas <ruta.xlsx>` que lee las hojas `CONSOLIDADO VENTAS` (o las `N8N_*` por canal) y puebla `ConsolidatedSale` + `SaleItem` + Vendedores.
- Debe: normalizar tipos (dinero a Decimal, fechas), resolver vendedores, deduplicar, y respetar la regla de solo-válidas (o cargar todo con su `status` real y marcar `state` según corresponda).
- Es la vía preferida para migrar los ~1.400 registros reales existentes de una sola vez.

> Nota sobre el archivo fuente: las hojas usan fórmulas (`FILTER`, `SPLIT`, `DUMMYFUNCTION`) y floats; el importador debe leer **valores calculados**, no fórmulas, y castear a los tipos del ERP.

---

## 8. API (borrador de endpoints)

```
# Webhooks (entrada externa)
POST /api/v1/webhooks/woocommerce/order-created/
POST /api/v1/webhooks/woocommerce/order-updated/
POST /api/v1/webhooks/kommo/lead-status-changed/

# Consolidado
GET  /api/v1/sales/                 # lista, filtros por TODAS las columnas, paginado
GET  /api/v1/sales/{id}/
PATCH/api/v1/sales/{id}/            # edición (auditada)
POST /api/v1/sales/bulk-update/     # edición masiva
POST /api/v1/sales/import/          # CSV (dry-run + commit)
POST /api/v1/sales/{id}/withdraw/   # retirar del consolidado

# Fuentes
POST /api/v1/sales/ferias/          # formulario ferias
POST /api/v1/sales/manual/          # formulario manual
POST /api/v1/sales/ecommerce/resync/  # reconciliación por rango de fechas (WooCommerce REST)

# Vendedores
GET/POST/PATCH/DELETE /api/v1/sellers/

# Reprocesar eventos
GET  /api/v1/integrations/events/?status=FAILED
POST /api/v1/integrations/events/{id}/reprocess/

# Métricas
GET  /api/v1/analytics/sales/summary/?from=&to=&compare=prev
GET  /api/v1/analytics/sales/by-channel/?...
GET  /api/v1/analytics/sales/by-seller/?...
GET  /api/v1/analytics/sales/by-city/?scope=historic|month
GET  /api/v1/analytics/sales/timeseries/?granularity=day|week|month
```

---

## 9. Panel de métricas (reemplazo del Looker actual)

El panel debe contener, como mínimo, lo que hoy está en Looker (ver imagen de referencia). Estructura:

**Vista global (todas las ventas consolidadas):**
- KPIs: Meta de ventas, Ventas del período, Performance % (vs meta), Proyección, Venta diaria esperada, Venta a la fecha, VDE en unidades. Con comparación vs período anterior (día/semana/mes) y % de variación.
- **Ventas por día de la semana** (mes actual + histórico) — barras.
- **Ventas diarias** (línea): ventas reales vs venta diaria esperada vs promedio de venta.
- **Serie temporal anual** comparando año actual vs anterior (línea, por mes).
- **Ventas por ciudad** (histórico y este mes) — pie/treemap. Requiere `city_raw` normalizada (usar `geo`).

**Vista por canal** (Ecommerce, Kommo, Ferias, Manual): misma estructura filtrada por `source`.

**Vista por comercial** (cada Vendedor): mismos KPIs + ventas por día + ventas por ciudad + serie temporal, filtrado por `seller`. (En el Looker actual existen paneles "Vendedora 1", "Ecommerce", etc.)

Filtros globales: rango de fechas, canal, vendedor, ciudad, estado.

Implementación: endpoints en `analytics` que agregan sobre `ConsolidatedSale` (con `state='ACTIVE'`), devolviendo series listas para graficar. Considerar vistas materializadas / agregados cacheados para desempeño. Comparativos período-a-período calculados en el servicio.

> Recordatorio de estética: gráficas con la paleta Seeds (verdes/crema/vino/salvia/terracota), no el azul/magenta genérico del Looker actual.

---

## 10. Casos límite y recovery (obligatorio)

| Caso | Manejo |
|---|---|
| Webhook llega pero el ERP está caído | Plugin WooCommerce reintenta con cola local; Kommo reintenta; además `RawWebhookEvent` + resync por rango. |
| Payload malformado / campo faltante | Persistir crudo, marcar `FAILED`, no romper; panel de reproceso. Cédula: buscar por key, no por índice. |
| Ciudad/dirección vacía o basura ("Domicilio", ".", "Recoger") | Marcar venta para revisión; no promover a logística hasta normalizar (ver `02`). |
| Orden duplicada (mismo order_id) | Upsert por `(source, external_id)`; nunca duplica. |
| Estado cambia después de consolidar | Webhook order-updated promueve/retira según §7.3. |
| Vendedor desconocido en texto crudo | Crear Vendedor "por revisar", no perder la venta. |
| Valor 0 / envío 0 | Permitido (hay casos reales); IVA/neto = 0. |
| Reventa de un lead ya cerrado | `old_status_id`/`status_id` + dedupe evitan doble consolidación. |
| Import CSV con filas mixtas válidas/ inválidas | Dry-run + reporte; inserta solo válidas, reporta el resto. |

Toda operación crítica deja `AuditLog`. Ningún fallo de un paso descarta el dato original.
