# Seeds ERP — 04 · Módulo de Contabilidad

> Requiere `00_ARQUITECTURA` (§9 integraciones, §10 masivas, §13 fiscal) y `01_VENTAS` (Consolidado).
> App: `apps/accounting`. Integración: **Alegra** (`https://api.alegra.com/api/v1/`, **HTTP Basic** con email + token; sandbox disponible).
> Dos submódulos: **Contabilidad/Facturación** y **Manejo de IVA**. Más **Reembolsos**.

> ⚠️ **Advertencia fiscal (la más importante del sistema):** emitir una factura la reporta a la DIAN y es irreversible. Un fallo que provoque doble emisión tiene implicaciones fiscales reales. Toda la lógica de este módulo es **idempotente y con control de doble emisión**. Nunca reintentar a ciegas: reintentar solo tras confirmar que la factura anterior NO fue aceptada.

---

## 1. Modelos

```python
class Customer(BaseModel):                 # deriva de usuarios/ventas
    user            = FK(users.User, null=True, blank=True)
    name            = CharField()
    id_type         = CharField()          # CC/NIT/CE...
    id_number       = CharField(db_index=True)
    email           = EmailField(blank=True)
    phone           = CharField(blank=True)
    address         = CharField(blank=True)
    city            = CharField(blank=True)
    alegra_id       = CharField(blank=True, db_index=True)   # id del contacto en Alegra
    alegra_synced   = BooleanField(default=False)
    class Meta: constraints=[UniqueConstraint(fields=['id_type','id_number'], name='uq_customer_doc')]

class Invoice(BaseModel):
    sale            = OneToOne(sales.ConsolidatedSale, related_name='invoice')
    customer        = FK(Customer)
    status          = CharField(choices=InvoiceStatus, default='POR_GENERAR')
    alegra_id       = CharField(blank=True, db_index=True)
    number          = CharField(blank=True)         # número de factura devuelto por Alegra
    cufe            = CharField(blank=True)          # CUFE DIAN si aplica
    pdf_url         = URLField(blank=True)
    total           = Decimal()
    iva             = Decimal(default=0)
    last_error      = TextField(blank=True)
    attempts        = IntegerField(default=0)
    idempotency_key = CharField(unique=True)         # = sale.source:external_id
    sent_at         = DateTimeField(null=True)       # cuándo se envió a Alegra
    confirmed_at    = DateTimeField(null=True)

class Refund(BaseModel):
    invoice         = FK(Invoice)
    sale            = FK(sales.ConsolidatedSale)
    status          = CharField(choices=RefundStatus, default='SOLICITADO')
    reason          = TextField()
    alegra_credit_note_id = CharField(blank=True)
    manual_void_pending   = BooleanField(default=True)  # "anular factura en el sistema contable"
    created_by      = FK(users.User, null=True)
```

### 1.1 Estados de `Invoice`
```
POR_GENERAR ──enviar a Alegra──> ENVIANDO ──confirmación OK──> GENERADA
     │                              │
     │                              └── error ──> FALLIDA ──[reintentar seguro]──> POR_GENERAR
     └── (nunca doble envío: guard por idempotency_key + estado)
GENERADA ──reembolso──> ANULADA
```
### 1.2 Estados de `Refund`
```
SOLICITADO → NOTA_CREDITO_EMITIDA → (manual_void_pending=True hasta confirmar en sistema contable) → CERRADO
```

---

## 2. Sincronización de clientes con Alegra

Requisito: cada vez que se crea un **cliente**, crearlo también en Alegra y guardar el `alegra_id` para poder facturar después.

Servicio `sync_customer_to_alegra(customer)`:
1. Idempotencia: si `customer.alegra_id` ya existe → no recrear. Buscar primero por identificación en Alegra (`GET /contacts?identification=`) para no duplicar contactos.
2. `POST /api/v1/contacts` (Basic Auth) con `{name, identification, email, phone, address, type:['client']}` según esquema Alegra.
3. Guardar `alegra_id`, `alegra_synced=True`. Registrar en `IntegrationLog`.
4. Fallo → reintentable; el cliente existe en el ERP igual (no se pierde).

Disparador: al crear `Customer` (derivado de una venta consolidada o de usuarios). Cuando llega una venta al consolidado, si no hay `Customer` para esa cédula, se crea (y se sincroniza con Alegra en background).

> Verificar contra la doc viva de Alegra (`https://developer.alegra.com/`) los nombres exactos de campos de `contacts` e `invoices` antes de implementar; el esquema puede variar por país/versión.

---

## 3. Registro "factura por generar" automático

Requisito: cada venta del consolidado deja un registro de factura por crear, con todos los datos necesarios.

- Al promover una venta a `ConsolidatedSale` (`01_VENTAS §3`), señal → crear `Invoice(status=POR_GENERAR)` con `idempotency_key = source:external_id`, `customer` resuelto/creado, totales e IVA calculados.
- La tabla de facturación muestra estos registros con un botón **Generar factura** por fila.

---

## 4. Generación de factura (Alegra) — idempotente

Servicio `issue_invoice(invoice)` — **el más delicado del sistema**:

1. **Guard de doble emisión:** si `invoice.status == GENERADA` o tiene `alegra_id`/`number` → abortar (ya emitida). Si `status == ENVIANDO` → abortar (hay un envío en curso; no relanzar).
2. Verificar `customer.alegra_id` (sincronizar si falta).
3. Marcar `ENVIANDO`, `sent_at=now`, persistir **antes** de llamar (así, si el proceso muere, sabemos que hubo un envío en vuelo y NO reintentamos a ciegas).
4. `POST /api/v1/invoices` (Basic Auth) con el payload Alegra: cliente (`client.id = alegra_id`), ítems (producto/precio/impuesto IVA 19%), fecha, forma de pago, numeración. Enviar un **header/campo de idempotencia** si Alegra lo soporta; si no, la protección es el estado + verificación posterior.
5. **Respuesta OK:** guardar `alegra_id`, `number`, `cufe`, `pdf_url`; `status=GENERADA`, `confirmed_at=now`. Enlazar al registro.
6. **Error/timeout:** `status=FALLIDA`, guardar `last_error`. **No** reintentar automáticamente. Antes de permitir *reintentar*, ejecutar `reconcile_invoice()`:
   - Consultar Alegra (`GET /invoices?...` por cliente/fecha/valor o por la referencia enviada) para saber si la factura **sí** se creó pese al error de red.
   - Si existe → adoptarla (`GENERADA`, guardar datos), **no** re-emitir.
   - Si no existe → habilitar reintento seguro (vuelve a `POR_GENERAR`).
7. Todo queda en `IntegrationLog` + `AuditLog`.

### 4.1 Generación masiva
Patrón `BatchJob` (`00 §10`): seleccionar N facturas `POR_GENERAR` → **una a una, secuencial** (concurrencia 1, throttle) para no ser bloqueados por Alegra. Cada ítem pasa por `issue_invoice` con todos sus guards. Progreso en vivo. Ningún ítem tumba el lote.

---

## 5. Reembolsos

Requisito: emitir un "reembolso" que anule la factura en el sistema contable, retire la venta de las tablas de ventas (para no tener cifras ciegas) y la deje en estado reembolsado; además dejar constancia de "anular factura" pendiente en el sistema contable.

Servicio `create_refund(invoice, reason)`:
1. Crear `Refund(status=SOLICITADO)`.
2. **Nota crédito en Alegra:** `POST /api/v1/credit-notes` referenciando la factura (`alegra_id`) → anula fiscalmente. Guardar `alegra_credit_note_id`, `status=NOTA_CREDITO_EMITIDA`. (Con la misma idempotencia/reconciliación del §4: no emitir doble nota crédito.)
3. **Retirar la venta de ventas:** `withdraw_from_consolidated(sale, reason='REFUND')` → `sale.state=REFUNDED`. Desaparece de tablas y métricas de ventas (descuenta la venta; evita cifras ciegas).
4. **Reversa de inventario** si el pedido ya había descontado stock: `KardexEntry(IN)` compensatorio (ver `03 §6`).
5. Marcar `invoice.status=ANULADA`.
6. `manual_void_pending=True`: queda en una sección/bandeja "anular factura" para que contabilidad confirme la anulación en el sistema contable externo; al confirmar → `manual_void_pending=False`, `Refund.CERRADO`.

---

## 6. Submódulo Manejo de IVA
- Vista de IVA generado por período (19%), a partir de `Invoice`/`ConsolidatedSale` (`iva_generated`, `net_value` — fórmulas de `00 §7.5`).
- Reportes por rango de fechas, canal, con exportación.
- Base para conciliación fiscal; no emite nada a la DIAN por sí mismo (eso es vía factura/nota crédito).

---

## 7. API (borrador)
```
# Clientes
GET/POST/PATCH /api/v1/accounting/customers/
POST /api/v1/accounting/customers/{id}/sync-alegra/

# Facturas
GET  /api/v1/accounting/invoices/?status=&from=&to=      # filtros por todas las columnas
POST /api/v1/accounting/invoices/{id}/issue/             # generar (con guards)
POST /api/v1/accounting/invoices/{id}/reconcile/         # verificar en Alegra
POST /api/v1/accounting/invoices/bulk-issue/             # masivo secuencial {ids:[]}
GET  /api/v1/accounting/invoices/{id}/                   # detalle + pdf/cufe

# Reembolsos
POST /api/v1/accounting/refunds/                         # {invoice_id, reason}
POST /api/v1/accounting/refunds/{id}/confirm-void/       # cierra manual_void_pending
GET  /api/v1/accounting/refunds/?status=

# IVA
GET  /api/v1/accounting/iva/summary/?from=&to=&channel=
```

## 8. Casos límite y recovery (fiscal-crítico)
| Caso | Manejo |
|---|---|
| Timeout al emitir (¿se creó o no?) | `reconcile_invoice` consulta Alegra antes de cualquier reintento. **Nunca** re-emitir a ciegas. |
| Doble click / doble envío | Guard por `status` + `idempotency_key` unique; `ENVIANDO` bloquea reenvío. |
| Cliente sin `alegra_id` | Sincronizar primero; si falla, factura queda `POR_GENERAR` con motivo. |
| Alegra rate limit | Masivo 1-a-1 con throttle. |
| Reembolso de factura no generada | Solo se anula lo `GENERADA`; si estaba `POR_GENERAR`, se cancela sin nota crédito. |
| Reembolso parcial | (Fase 2) nota crédito por monto parcial. |
| Nota crédito duplicada | Idempotencia por `invoice` + reconciliación. |
| Venta retirada que ya tenía guía/inventario | Reversa de inventario; la guía se gestiona aparte (cancelación en `02` fase 2). |

Todo movimiento fiscal deja `IntegrationLog` (request/response Alegra) + `AuditLog` (actor, acción, entidad).
