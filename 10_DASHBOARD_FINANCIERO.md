# Seeds ERP — 10 · Dashboard de Control (Torre de Control)

> Requiere todos los módulos anteriores (agrega sus datos). App: `apps/dashboard` (se apoya en `analytics`).
> No confundir con el **panel de métricas de ventas** (`01_VENTAS §9`, reemplazo de Looker), que mide desempeño comercial. Este es un **dashboard operativo de control**: muestra lo que está mal, incompleto o pendiente para que nada se escape — empezando por "gastos sin factura" y todos sus equivalentes en cada módulo.

La idea: una sola pantalla donde el equipo ve, de un vistazo, el estado de salud del sistema y las cosas que requieren acción. Cada indicador es accionable (lleva al listado filtrado que lo origina).

---

## 1. Concepto

Dos tipos de contenido:

1. **Indicadores de control (health checks):** conteos y montos de cosas pendientes o inconsistentes — gastos sin factura, facturas fallidas, guías fallidas, ventas sin clasificar, movimientos bancarios sin clasificar, descuadres de auditoría, etc. Cada uno con su umbral y severidad.
2. **KPIs de estado:** métricas de completitud y salud — % de gastos con soporte, % de movimientos clasificados, % de ventas facturadas, antigüedad del dato más viejo sin resolver.

Todo indicador es **parametrizable** desde configuración (`07`): umbrales, severidad, si aparece en el dashboard, a qué rol se muestra.

---

## 2. Modelo de datos

En vez de duplicar datos, el dashboard **calcula indicadores en vivo** a partir de los módulos, con una capa fina de definición y cache:

```python
class ControlIndicator(BaseModel):          # definición (parametrizable)
    key          = CharField(unique=True)    # "gastos_sin_factura"
    label        = CharField()               # "Gastos sin factura"
    module       = CharField()               # EXPENSES/SALES/LOGISTICS/FINANCE/ACCOUNTING/INVENTORY
    description  = CharField(blank=True)
    unit         = CharField()               # COUNT / AMOUNT / PERCENT / DAYS
    severity     = CharField(choices=[('INFO','Info'),('WARNING','Warning'),('CRITICAL','Crítico')])
    warn_threshold  = Decimal(null=True)     # a partir de aquí, warning
    crit_threshold  = Decimal(null=True)     # a partir de aquí, crítico
    target_url   = CharField()               # ruta al listado filtrado que lo origina (drill-down)
    visible      = BooleanField(default=True)
    roles        = JSONField(default=list)   # roles que lo ven
    order        = IntegerField(default=0)

class IndicatorSnapshot(BaseModel):          # histórico para tendencias
    indicator = FK(ControlIndicator)
    value     = Decimal()
    amount    = Decimal(null=True)           # monto asociado si aplica
    captured_at = DateTimeField(auto_now_add=True)
```

Cada indicador tiene un **resolver** en código (`dashboard/resolvers/<key>.py`) que ejecuta el conteo/consulta sobre los selectores del módulo correspondiente. Un task de Celery Beat toma snapshots periódicos (para tendencias); el valor "ahora" se calcula on-demand con cache corto.

---

## 3. Catálogo de indicadores (seed inicial)

Enumerados por módulo. El agente los implementa como resolvers; el usuario ajusta umbrales/visibilidad después.

### 3.1 Gastos (`09`) — el que pediste primero
- **Gastos sin factura** — `Expense` en `FACTURA_SIN_SOPORTE` o sin adjunto `PROVIDER_INVOICE`. Conteo + monto. *Crítico* (riesgo fiscal).
- **Gastos sin comprobante de pago** — sin adjunto `PAYMENT_PROOF`.
- **Gastos sin cuenta EFE** — registrados pero sin `efe_account` (no cuentan en el modelo).
- **Reembolsos por pagar** — `REEMBOLSOS_POR_PAGAR`: cuánto se debe y a quién, con antigüedad.
- **Cuentas por pagar** — `CUENTAS_POR_PAGAR`: obligaciones pendientes + vencimiento.
- **IVA por descontar** — facturas con `iva_discountable` y `iva_already_discounted=False`.
- **Gastos sin conciliar** — sin `bank_movement` enlazado.

### 3.2 Finanzas (`08`)
- **Movimientos bancarios sin clasificar** — `BankMovement` en `POR_CLASIFICAR`, por banco. % clasificado.
- **Descuadres de auditoría de ingresos** — días/bancos donde `|validación| > tolerancia` (reportes ≠ bancos).
- **Egresos bancarios sin gasto documentado** — egresos sin `Expense` conciliado.
- **Interbancarias sin marcar** — posibles transferencias no marcadas `is_interbank` (heurística por concepto/monto espejo).
- **Meses sin cerrar** — periodos EFE abiertos con % de clasificación < 100.

### 3.3 Contabilidad (`04`)
- **Facturas fallidas** — `Invoice` en `FALLIDA` (error Alegra). *Crítico.*
- **Facturas por generar** — `POR_GENERAR` con antigüedad (ventas sin facturar).
- **Facturas en `ENVIANDO` colgadas** — llevan demasiado tiempo en envío (posible timeout → requiere reconciliación, `04 §4.6`). *Crítico.*
- **Clientes sin sincronizar con Alegra** — `Customer.alegra_synced=False`.
- **Reembolsos con anulación pendiente** — `Refund.manual_void_pending=True`.

### 3.4 Ventas (`01`)
- **Ventas sin vendedor resuelto** — Vendedor "por revisar".
- **Ventas con ciudad/dirección inválida** — bloqueadas para logística.
- **Eventos de webhook fallidos** — `RawWebhookEvent` en `FAILED` (Woo/Kommo), por reprocesar.
- **Ventas sin cliente** — sin `Customer` asociado (afecta facturación).

### 3.5 Logística (`02`)
- **Guías fallidas** — `Shipment` en `GUIA_FALLIDA`. Conteo + antigüedad.
- **Pedidos por generar guía** — `POR_GENERAR` acumulados.
- **Guías con warning de destino** — `warning=True` (destino generado ≠ pedido). *Warning.*
- **Pedidos listos para enviar sin despachar** — antigüedad en `LISTO_PARA_ENVIAR`.

### 3.6 Inventario (`03`)
- **Productos con stock bajo** — `stock <= reorder_level`.
- **Stock negativo** — productos por debajo de cero.
- **Ventas enviadas sin descuento de inventario** — inconsistencias de kardex.
- **Productos sin mapear** — ventas con color/tipo sin `Product`.

### 3.7 Sistema
- **Integraciones caídas** — última llamada a Envia/Alegra/Woo/Kommo con error (de `IntegrationLog`).
- **Credenciales faltantes o en sandbox** — desde `07` (aviso si producción usa sandbox).
- **Tareas Celery fallidas** — jobs en error sin reintento exitoso.

---

## 4. Pantalla

**Home del dashboard** (landing tras login, según rol):

- **Fila de alertas críticas** arriba: tarjetas rojas (vino Seeds) con los indicadores `CRITICAL` que superan umbral — p.ej. "Gastos sin factura: 12 · $3.4M", "Facturas fallidas: 2". Clic → listado filtrado.
- **Cuadrícula de indicadores** por módulo, cada tarjeta con: valor actual, monto asociado, mini-sparkline de tendencia (de `IndicatorSnapshot`), color por severidad (salvia OK / arcilla warning / vino crítico), y enlace de drill-down.
- **Filtros globales:** rango de fechas, módulo, severidad, responsable.
- **Vista por rol:** contabilidad ve gastos/facturas/finanzas; logística ve guías/despachos/inventario; admin ve todo. Configurable.
- **"Requiere mi acción":** sección personalizada por usuario (lo asignado o creado por él que está pendiente).

Semántica de color = la de `06 §3.2` (salvia/arcilla/vino sobre crema). Tarjetas con la estética Seeds, sparklines con la paleta, sin rojos/amarillos genéricos.

### 4.1 Drill-down
Cada indicador enlaza al listado del módulo con el filtro ya aplicado (usa el `DataTable` de `06 §5.1` con una vista guardada). "Gastos sin factura" → tabla de gastos filtrada por `FACTURA_SIN_SOPORTE`, lista para actuar (adjuntar factura, cambiar estado, edición masiva).

---

## 5. Alertas y notificaciones (opcional, fase 2)

- Cuando un indicador cruza a `CRITICAL`, generar notificación in-app (y opcional email/Slack) al rol responsable.
- Digest diario/semanal configurable: resumen de pendientes por módulo.
- Silenciar/snooze por indicador.

---

## 6. API (borrador)

```
GET  /api/v1/dashboard/                       # todos los indicadores visibles para el rol (valor + tendencia)
GET  /api/v1/dashboard/{key}/                 # detalle de un indicador + histórico
GET  /api/v1/dashboard/{key}/items/           # los registros que lo componen (o redirige al listado del módulo)
GET  /api/v1/dashboard/my-actions/            # pendientes del usuario
# Config
GET/PATCH /api/v1/dashboard/indicators/       # umbrales, visibilidad, roles (parametrizable, ADMIN)
```

---

## 7. Parametrización (desde `07`)

Sección **Dashboard** en configuración: por indicador, editar `label`, umbrales `warn/crit`, severidad, visibilidad, roles y orden. Crear indicadores nuevos (para los que exista resolver) o desactivar los que no interesen. El dashboard arranca con el catálogo seed de §3 y se ajusta sin tocar código.

---

## 8. Casos límite

| Caso | Manejo |
|---|---|
| Indicador pesado de calcular | Cache corto + snapshot periódico; cálculo on-demand solo al abrir. |
| Umbral no configurado | Se muestra como INFO sin color de alerta. |
| Rol sin permiso sobre el módulo del indicador | No se le muestra (los indicadores respetan permisos). |
| Drill-down a módulo restringido | Enlace oculto si el rol no puede ver el listado. |
| Doble conteo entre indicadores | Cada resolver define su consulta; se documenta qué cuenta cada uno. |
| Tendencia sin histórico aún | Sparkline vacío hasta acumular snapshots. |

Todo cambio de umbral/definición queda en `AuditLog`.