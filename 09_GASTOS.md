# Seeds ERP — 09 · Registro de Gastos

> Requiere `00_ARQUITECTURA`, `08_FINANZAS` (modelo financiero EFE, planes de cuentas, movimientos bancarios). App: `apps/expenses`.
> Reemplaza el sistema actual en **Notion** ("GESTIÓN DE GASTOS") + el Excel `FORMATEADOR DE GASTOS NOTION` + la hoja `IMPORT_REGISTRO_GASTOS` del modelo financiero.

Este módulo es la **fuente de los gastos del EFE**. Cada gasto se registra como una tarjeta con su comprobante de pago y la factura del proveedor, avanza por un pipeline de aprobación, se le atribuye una cuenta del modelo financiero, y al quedar registrado alimenta las líneas de gasto/costo del EFE (`08 §6`).

> Hallazgo clave de la reconstrucción: en el modelo actual, las líneas de **gasto y COGS** del EFE (`3.x`, `5.x`, `6.x`, `7.x`) hacen `SUMIFS` sobre `IMPORT_REGISTRO_GASTOS` por *cuenta EFE* y mes — es decir, se nutren de **este** módulo, no de los movimientos bancarios. Los movimientos bancarios (`08 §5`) alimentan la auditoría de ingresos y la conciliación de caja. Ambos se cruzan (un gasto se concilia contra su movimiento bancario), pero la atribución contable del gasto vive aquí.

> Nota: el archivo `FORMATEADOR_DE_GASTOS_NOTION.xlsx` no llegó en la carga (solo las imágenes). El formato destino se reconstruyó desde `IMPORT_REGISTRO_GASTOS` del modelo financiero, que es su salida. Si el formateador tiene columnas de transformación adicionales, se añaden al mapeo de §6 sin cambiar el diseño.

---

## 1. Modelo de datos

### 1.1 `Expense` (la tarjeta de gasto)

Campos tomados de la tarjeta de Notion (imagen 2) más lo necesario para el EFE:

```python
class Expense(BaseModel):
    title            = CharField()                    # "Reembolso cami por envío maria ximena garcia"
    concept          = CharField(blank=True)          # CONCEPTO para el EFE (default = title)
    amount           = Decimal()                      # "Monto"
    bank_account     = FK(finance.Bank)               # "Cuenta" (Bancolombia Seeds, Nequi Maji, MercadoPago…)
    expense_date     = DateField()                    # "Fecha del gasto"
    payment_date     = DateField(null=True)           # "Fecha de pago"
    # atribución al modelo financiero
    efe_account      = FK(finance.FinancialAccount, null=True)   # "CUENTA ATRIBUIDA DEL EFE"
    accounting_account = FK(finance.AccountingAccount, null=True) # PUC (opcional)
    attribution      = CharField(blank=True)          # ADMINISTRATIVO/VENTAS/OPERACIONAL...
    # pipeline
    status           = FK('ExpenseStatus')            # etapa del board (parametrizable, §2)
    responsible      = FK(users.User, null=True)      # "Responsable del gasto"
    checked          = BooleanField(default=False)    # "Checkeado"
    approved_by      = FK(users.User, null=True, related_name='approved_expenses')
    # IVA
    iva_discountable = Decimal(null=True)             # "IVA descontable"
    iva_already_discounted = BooleanField(default=False)  # "Iva ya descontado"
    # amortización (del formato IMPORT_REGISTRO_GASTOS)
    amortize         = BooleanField(default=False)    # "AMORTIZAR"
    amortization_months = IntegerField(null=True)     # "TIEMPO DE AMORTIZACIÓN"
    # conciliación con banco
    bank_movement    = FK(finance.BankMovement, null=True, blank=True)  # enlace al egreso real
    reconciled       = BooleanField(default=False)
    alegra_synced    = BooleanField(default=False)
    alegra_id        = CharField(blank=True)
    # trazabilidad
    created_by       = FK(users.User, null=True, related_name='created_expenses')
    # derivados (semana/mes/año) se calculan de expense_date en servicios/consultas
```

### 1.2 `ExpenseAttachment` (comprobante + factura)

Requisito explícito: cada tarjeta lleva en el cuerpo **el comprobante de la transacción** (imagen/PDF) y **la factura del proveedor**.

```python
class ExpenseAttachment(BaseModel):
    expense   = FK(Expense, related_name='attachments')
    kind      = CharField(choices=[('PAYMENT_PROOF','Comprobante de pago'),
                                    ('PROVIDER_INVOICE','Factura del proveedor'),
                                    ('OTHER','Otro')])
    file      = FileField(...)          # imagen, PDF, etc. (ver §4 almacenamiento)
    filename  = CharField()
    mime_type = CharField()
    uploaded_by = FK(users.User, null=True)
```

### 1.3 Estados del pipeline (`ExpenseStatus`, parametrizable)

Reproduce las columnas del board de Notion (imagen 1), pero editables desde configuración:

| Estado (seed) | Significado |
|---|---|
| `REEMBOLSOS_POR_PAGAR` | Dinero que la empresa debe a alguien que pagó de su bolsillo (p.ej. envíos). |
| `CUENTAS_POR_PAGAR` | Facturas/obligaciones pendientes de pago. |
| `GASTOS_POR_REGISTRAR` | Gastos por documentar/clasificar. |
| `GASTOS_REGISTRADOS` | **Gasto documentado y atribuido → alimenta el EFE.** |
| `FACTURAS_PARA_DESCONTAR` | Facturas cuyo IVA aún no se ha descontado. |
| `FACTURAS_DE_DESCUENTO` | Facturas con IVA descontable procesado. |
| `FACTURA_SIN_SOPORTE` | Gasto sin factura/soporte del proveedor (riesgo fiscal → alerta). |
| `DOCUMENTO_CONTABLE` | Registrado como documento contable. |
| `PAGOS_POR_CONTABILIZAR` | Pagos hechos, pendientes de contabilizar. |
| `DOCUMENTO_SOPORTE` | Soporte documental archivado. |

```python
class ExpenseStatus(BaseModel):
    key      = CharField(unique=True)
    label    = CharField()
    order    = IntegerField()
    feeds_efe = BooleanField(default=False)   # True solo en GASTOS_REGISTRADOS (configurable)
    color    = CharField(blank=True)          # paleta Seeds
    active   = BooleanField(default=True)
```

`feeds_efe` marca qué etapa(s) hacen que el gasto cuente en el modelo financiero. Por defecto solo `GASTOS_REGISTRADOS`, replicando "cuando paso a gasto registrado, esto se va al formateador".

---

## 2. Pipeline y sub-flujos

El módulo es, como en Notion, un **tablero Kanban** con estas vistas (pestañas de imagen 1): **Board**, **Table**, **Reembolsos**, **IVA**.

- **Board:** columnas = `ExpenseStatus`, tarjetas arrastrables. Drag&drop cambia el estado (con las reglas de §2.1). Cada tarjeta muestra título, cuenta (tag de color), fecha, monto, responsables — igual que Notion.
- **Table:** la misma data en tabla densa, con filtro por todas las columnas y edición masiva (`00 §11`).
- **Reembolsos:** vista filtrada de gastos que son reembolsos a personas (`REEMBOLSOS_POR_PAGAR` → pagados), para saber cuánto se debe y a quién.
- **IVA:** vista de facturas con IVA descontable (`iva_discountable`, `iva_already_discounted`) para gestionar el descuento — conecta con el manejo de IVA de `04 §6`.

### 2.1 Transición a `GASTOS_REGISTRADOS` (la que alimenta el EFE)

Al pasar una tarjeta a un estado con `feeds_efe=True`, el sistema **valida** antes de aceptar:
- `efe_account` asignada (obligatoria — es la cuenta del modelo financiero).
- `amount`, `expense_date`, `bank_account` presentes.
- Comprobante de pago adjunto (advertencia si falta; bloqueo configurable).
- Si es un gasto que requiere factura y no la tiene → sugiere `FACTURA_SIN_SOPORTE` en su lugar.

Cumplido esto, el gasto queda "registrado" y entra al cálculo del EFE (§6). Si falla una validación, la transición se rechaza con motivo claro (igual que las transiciones inválidas del Kannban en `06 §5.3`).

---

## 3. Atribución a cuentas del EFE

El corazón del módulo: asignar a cada gasto su **cuenta del modelo financiero** (`FinancialAccount`, `08 §2.1`). Ejemplos reales de atribución vistos en los datos: `1.3 DEVOLUCIÓN EN VENTAS` (reembolsos), `3.1 Raw M` (materia prima), `6.1.1.1 Salarios`, `7.2 GASTOS DE PUBLICIDAD`.

- Selector de cuenta EFE en la tarjeta (árbol jerárquico, solo hojas imputables).
- **Auto-sugerencia por reglas** (reutiliza `ClassificationRule` de `08 §5.3`): por concepto/proveedor/cuenta bancaria sugiere la cuenta EFE (p.ej. títulos que empiezan por "Reembolso … envío" → `1.3` o la cuenta de fletes; "Honorarios …" → gasto de personal). El usuario confirma o corrige.
- Edición masiva: seleccionar N gastos del mismo tipo → atribuir la misma cuenta.

---

## 4. Archivos (comprobantes y facturas)

- Almacenamiento en object storage (S3/MinIO); en la BD solo metadatos + ruta.
- Tipos: imagen (JPG/PNG), PDF. Vista previa en la tarjeta.
- Dos roles de archivo por gasto: **comprobante de pago** (la transacción) y **factura del proveedor**. Puede haber varios.
- Validaciones: tamaño máximo, tipos permitidos, antivirus opcional.
- Un gasto en `FACTURA_SIN_SOPORTE` es, precisamente, el que no tiene `PROVIDER_INVOICE` → el sistema lo detecta y lo resalta (riesgo fiscal).

---

## 5. Amortización (gastos diferidos) — cálculo automático

Del formato destino: `AMORTIZAR` + `TIEMPO DE AMORTIZACIÓN`. Un gasto puede repartirse en varios meses dentro del EFE en lugar de golpear un solo mes. **El sistema hace el reparto solo**, sin intervención manual.

### 5.1 Regla (sin ambigüedad)

Sea `N` = número de meses de amortización:

```
N = amortization_months  si  amortize == True  y  amortization_months >= 1
N = 1                     en cualquier otro caso
```

Es decir: **si el gasto no está marcado como amortizable, o está marcado pero sin meses (vacío/0/1), N = 1** y el gasto entra completo en su mes. No hay estado intermedio ni error: siempre hay un `N` válido ≥ 1.

- **Monto por mes** = `amount / N` (Decimal, 2 decimales). El **redondeo** se ajusta en la última cuota para que la suma de las N cuotas sea exactamente `amount` (sin centavos perdidos).
- **Mes de inicio** = mes de `expense_date` (parametrizable a `payment_date` si el negocio lo prefiere; por defecto `expense_date`).
- Se generan `N` imputaciones mensuales consecutivas a partir del mes de inicio, todas con la **misma cuenta EFE** y **misma atribución** del gasto.

Ejemplos:
- Licencia anual $1.200.000, `amortize=True`, `N=12` → 12 cuotas de $100.000, de su mes de inicio en adelante.
- Gasto $50.000 sin marcar amortizable → `N=1` → una imputación de $50.000 en su mes.
- Gasto marcado amortizable pero con meses vacío → `N=1` (se asume 1).

### 5.2 Implementación

```python
class ExpenseAmortizationEntry(BaseModel):
    expense = FK(Expense, related_name='amortization_entries')
    period_month = IntegerField()      # 1..12
    period_year  = IntegerField()
    amount       = Decimal()           # cuota del mes (la última absorbe el redondeo)
    efe_account  = FK(finance.FinancialAccount)   # se copia del gasto (histórico estable)
    class Meta:
        constraints=[UniqueConstraint(fields=['expense','period_month','period_year'],
                     name='uq_amort_period')]
```

- Al registrar el gasto (transición a `feeds_efe`) o al cambiar `amount`/`amortize`/`amortization_months`/fecha, el servicio **regenera** las `ExpenseAmortizationEntry` (borra y recrea las del gasto). Es idempotente: recalcular siempre produce el mismo set.
- Estas entradas —no el gasto directamente— son las que suma el EFE. Un gasto con `N=1` produce exactamente una entrada, así el EFE tiene una sola fuente uniforme (amortizados y no amortizados se tratan igual).
- **Cierres de mes** (`08 §6`): si alguna cuota cae en un mes ya cerrado, esa cuota requiere reapertura auditada del mes; las cuotas de meses abiertos se actualizan normalmente. El servicio avisa qué meses se verían afectados antes de confirmar.

> Regla de negocio a confirmar: si un gasto amortizado se **reembolsa/anula** a mitad de camino, por defecto se eliminan las cuotas de meses **aún no cerrados** y se conservan las de meses cerrados (ya reportados). Parametrizable.

---

## 6. Alimentación del modelo financiero (reemplazo del formateador)

Reemplaza la cadena *Notion → formateador Excel → IMPORT_REGISTRO_GASTOS → EFE*. Ahora es directo:

Los gastos con estado `feeds_efe=True` producen imputaciones que el EFE consume. Formato objetivo (columnas de `IMPORT_REGISTRO_GASTOS`, ya nativas en el modelo):

| Columna destino | Origen en `Expense` |
|---|---|
| FECHA | `expense_date` |
| SEMANA / MES / AÑO | derivados de la fecha |
| CONCEPTO | `concept` (o `title`) |
| MONTO | `amount` (entra negativo en las líneas de gasto del EFE) |
| CUENTA ATRIBUIDA DEL EFE | `efe_account.full_label` |
| CUENTA | `bank_account.name` |
| AMORTIZAR | `amortize` |
| TIEMPO DE AMORTIZACIÓN | `amortization_months` |
| IVA | `iva_discountable` |

El servicio `build_efe` (`08 §6`) suma estas imputaciones por cuenta EFE y mes en las líneas `3.x/5.x/6.x/7.x`. **La unidad que suma el EFE es la cuota mensual (`ExpenseAmortizationEntry`), no el gasto**: un gasto no amortizable produce una sola cuota (N=1) en su mes; uno amortizable produce N cuotas en meses consecutivos (§5). Así el modelo trata ambos de forma uniforme y el diferido queda reflejado automáticamente. No hay import manual ni Excel intermedio: el gasto registrado ya está en el modelo. Un cambio de atribución, de amortización o un reembolso recalcula el EFE de los meses afectados (respetando cierres de mes, `08 §6`).

---

## 7. Conciliación con movimientos bancarios (`08`)

Cada gasto tiene un pago real que aparece como **egreso** en un extracto bancario (`finance.BankMovement`). El módulo permite enlazar `Expense.bank_movement` para conciliar:
- Sugerencia automática de match por banco + monto + fecha aproximada.
- Al conciliar: `reconciled=True`; el movimiento bancario queda marcado como respaldado por un gasto documentado.
- Reporte de descuadres: egresos bancarios sin gasto documentado, y gastos sin egreso bancario (p.ej. reembolso aún no pagado). Esto cierra el círculo entre "lo que gasté" (documentado) y "lo que salió del banco" (real).

---

## 8. Registro en Alegra (opcional, fase 2)

`alegra_synced`/`alegra_id` para registrar el gasto/factura de proveedor en Alegra (compras, IVA descontable). Misma idempotencia y logging de `04`. Por ahora basta el marcador para el flujo de IVA.

---

## 9. API (borrador)

```
GET/POST/PATCH/DELETE /api/v1/expenses/                 # tablero/tabla, filtros por todas las columnas
POST  /api/v1/expenses/{id}/attachments/                # subir comprobante / factura
POST  /api/v1/expenses/{id}/transition/                 # cambiar de estado (valida reglas)
POST  /api/v1/expenses/bulk-update/                     # edición/atribución masiva
POST  /api/v1/expenses/{id}/reconcile/                  # enlazar a BankMovement
GET   /api/v1/expenses/reimbursements/                  # vista Reembolsos
GET   /api/v1/expenses/iva/                             # vista IVA descontable
GET   /api/v1/expenses/statuses/  (config)              # estados del pipeline (parametrizable)
```

---

## 10. Pantallas

- **Board (Kanban):** columnas parametrizables, tarjetas con cuenta/fecha/monto/responsables, drag&drop, adjuntos con preview. Estética Seeds.
- **Table:** tabla densa, filtro por todas las columnas, edición masiva, atribución EFE en lote.
- **Detalle de gasto:** todos los campos + comprobante de pago + factura del proveedor + estado + conciliación bancaria.
- **Reembolsos:** cuánto se debe, a quién, estado de pago.
- **IVA:** facturas con IVA descontable, descontado / por descontar.
- **Config → Gastos:** estados del pipeline, reglas de auto-atribución, validaciones por estado.

---

## 11. Casos límite y recovery

| Caso | Manejo |
|---|---|
| Gasto sin factura del proveedor | Estado `FACTURA_SIN_SOPORTE`, resaltado; no bloquea registro pero alerta (riesgo fiscal). |
| Gasto registrado sin cuenta EFE | La transición a `feeds_efe` la exige; sin ella no cuenta en el modelo. |
| Reembolso pendiente de pago | `REEMBOLSOS_POR_PAGAR`; visible en vista Reembolsos hasta que se paga y concilia. |
| Gasto amortizado | Se reparte en N meses (N=1 si no está marcado o sin meses); cambiarlo regenera todas las cuotas. Redondeo absorbido en la última cuota. |
| Doble carga del mismo gasto | Sin clave natural externa; se previene con detección de posibles duplicados (mismo monto+fecha+cuenta) y confirmación. |
| Cambio de atribución tras cierre de mes | Requiere reapertura auditada del mes (`08 §6`). |
| Egreso bancario sin gasto documentado | Aparece en el reporte de conciliación como pendiente de documentar. |
| Archivo corrupto / tipo no permitido | Validación al subir; el gasto no se pierde, el adjunto se rechaza con motivo. |
| Cambio de estados del pipeline | Parametrizable; los gastos guardan histórico de transiciones (`AuditLog`). |

Toda transición y atribución deja `AuditLog`. Los adjuntos son inmutables (nueva versión, no sobrescritura) para preservar el soporte.