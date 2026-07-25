# Seeds ERP — 08 · Finanzas: Modelo Financiero, Auditoría de Ingresos y Conciliación Bancaria

> Requiere `00_ARQUITECTURA`, `01_VENTAS` (Consolidado) y `04_CONTABILIDAD` (Alegra/facturas). App: `apps/finance`.
> Este módulo es la capa de **tesorería y control financiero**. `04` factura; `08` clasifica el dinero real que entra y sale, lo estructura en el modelo financiero (EFE) y **audita** que lo reportado por el equipo coincida con lo que realmente llegó a los bancos.

Reemplaza cuatro archivos de Google Sheets encadenados: `SD MODELO FINANCIERO`, `SD CONTROL DE INGRESOS Y EGRESOS`, `FORMATEADOR BANCOLOMBIA` y `SD VALIDACIÓN DIARIA DE CUENTAS`. En el ERP dejan de ser hojas con fórmulas y pasan a ser datos vivos alimentados por el consolidado de ventas y por la importación de extractos bancarios.

---

## 1. Concepto y flujo de datos

```
VENTAS (ConsolidatedSale, 01) ───────────────────────────────► Modelo Financiero (EFE): líneas de VENTAS (1.x)
        │  (live, sin import manual)                                        ▲
        │                                                                   │
Extractos bancarios (CSV):                                                  │ gastos/costos (3.x, 6.x, 7.x, 5.x)
  Bancolombia · MercadoPago · Bold · Nequi                                  │
        │                                                                   │
        ├─ Importador por banco ─► BankMovement (crudo normalizado:         │
        │     INGRESO/EGRESO por signo, fecha, dedup)                       │
        │            │                                                      │
        │            ├─ Clasificación: CUENTA EFE + CUENTA CONTABLE ────────┘
        │            │                 + ATRIBUCIÓN + BANCO
        │            │
        │            └─────────────────────────────► Auditoría de Ingresos (validación)
        │                                                     ▲
Reportes del equipo (ventas consolidadas + efectivo) ────────┘
        (lo que el equipo dice que entró, por banco y día)

Auditoría:  INGRESOS SEGÚN BANCOS (real)  −  INTERBANCARIOS ("Otros pasivos")  =  INGRESOS NETOS
            VALIDACIÓN = INGRESOS NETOS (bancos)  −  INGRESOS SEGÚN REPORTES   ──► gráfico de discrepancia
```

Dos ideas centrales que hay que respetar:

1. **Dos planes de cuentas conviven** (ambos parametrizables desde el panel, §3): la **Cuenta EFE** (estructura del modelo financiero, jerárquica) y la **Cuenta Contable** (PUC colombiano). Cada movimiento de dinero se clasifica en ambas.
2. **Las transferencias interbancarias no son ingreso.** Cuando MercadoPago o Bold liquidan a Bancolombia, ese dinero ya se contó como venta al recibirse; volver a contarlo al llegar a Bancolombia lo duplicaría. Por eso se clasifican como **"Otros pasivos"** y se excluyen del ingreso neto. Es la clave de toda la auditoría.

---

## 2. Planes de cuentas (parametrizables)

### 2.1 `FinancialAccount` — Cuenta EFE (modelo financiero)

Árbol jerárquico por código punteado. Ejemplos reales del modelo:

```
1. VENTAS NETAS
  1.1 VENTAS EARSEEDING
    1.1.1 Adquisición
      1.1.1.1 Ecommerce      ← ventas ecommerce
      1.1.1.2 Kommo          ← ventas kommo
    1.1.2 MRR (recurrente)
      1.1.2.1 Ecommerce
      1.1.2.2 Kommo
    1.1.3 Ferias
  1.2 Ventas flete
  1.3 Devolución en ventas
3. COGS (3.1 Raw M, 3.2 Manual, 3.3 Sobre, 3.4 Caja, 3.5 Bolsa envío)
4. INGRESO (RECAUDO)  (4.3.2 Rendimientos financieros, 4.4 Auditoría ingresos…)
6. COSTOS OPERATIVOS  (6.1.1 Salarios domicilios, 6.1.4 Warehousing, 6.4 Otros…)
7. GASTOS (7.1 Publicidad, 7.2 Gastos publicidad, 7.3 Personal ventas…)
5. GASTO ADMINISTRATIVO (5.1 Personal administrativo…)
```

```python
class FinancialAccount(BaseModel):
    code       = CharField(unique=True)      # "1.1.1.1"
    name       = CharField()                 # "Ecommerce"
    full_label = CharField()                 # "1.1.1.1. Ecommerce" (lo que usan las hojas para hacer match)
    parent     = FK('self', null=True)
    kind       = CharField(choices=[('VENTAS','Ventas'),('COGS','COGS'),
                 ('INGRESO','Ingreso/Recaudo'),('COSTO','Costo operativo'),
                 ('GASTO','Gasto'),('PASIVO','Otros pasivos'),('AJUSTE','Ajuste')])
    is_leaf    = BooleanField(default=True)   # solo las hojas reciben movimientos; los padres suman
    sign       = CharField(choices=[('IN','Entra'),('OUT','Sale')], blank=True)
    active     = BooleanField(default=True)
    order      = IntegerField(default=0)      # orden de presentación en el EFE
```

Los nodos padre (1, 1.1, 1.1.1) **se calculan** sumando hijos; solo las hojas reciben imputación directa. `full_label` es la clave de mapeo (las hojas hacían `SUMIFS` por ese texto).

### 2.2 `AccountingAccount` — Cuenta Contable (PUC)

Plan contable colombiano estándar, con atribución. Ejemplos reales: `51 Gastos de administración`, `5105 Gastos de personal`.

```python
class AccountingAccount(BaseModel):
    code        = CharField(unique=True)      # "5105"
    name        = CharField()                 # "Gastos de personal"
    attribution = CharField(choices=[('ADMINISTRATIVO','Administrativo'),('VENTAS','Ventas'),
                  ('OPERACIONAL','Operacional'),('COMPARTIDO','Compartido'),('NIAT','NIAT')])
    active      = BooleanField(default=True)
```

### 2.3 `Bank` — cuentas de banco/pasarela

```python
class Bank(BaseModel):
    name        = CharField(unique=True)   # BANCOLOMBIA, MERCADO PAGO, BOLD, NEQUI, PAYU, EFECTIVO
    kind        = CharField(choices=[('BANK','Banco'),('GATEWAY','Pasarela'),('CASH','Efectivo')])
    account_no  = CharField(blank=True)     # 60100006016
    importer    = CharField(blank=True)     # clave del parser de CSV (bancolombia|mercadopago|bold|nequi)
    active      = BooleanField(default=True)
```

---

## 3. Parametrización desde el panel (requisito explícito)

Todo lo anterior se administra desde el módulo de configuración (`07_CONFIGURACION`), sección **Finanzas**:

- **Árbol de cuentas EFE**: crear/editar/reordenar/activar, con vista de árbol drag&drop. El usuario define su modelo financiero.
- **Plan contable (PUC)** y atribuciones.
- **Bancos/pasarelas** y qué importador usa cada uno.
- **Reglas de auto-clasificación** (§5.3): "si banco = MERCADO PAGO y concepto contiene 'Cargo por cobrar' → EFE = Comisión MGF, contable = gasto financiero". Editable, ordenable, con prioridad.
- **Mapeo de reportes ↔ bancos** para la validación (§7): qué columna de "reportes" corresponde a qué banco real.
- **Marcador de interbancarias**: qué cuenta EFE representa "Otros pasivos" (interbancario) — el que se excluye del ingreso neto.

Nada de esto va hardcodeado. El sistema arranca con un seed del árbol actual del modelo, pero el usuario lo edita libremente.

---

## 4. Ventas → panel financiero (automático)

Requisito: *todas las ventas de Kommo, Ecommerce, etc. deben quedar en el panel financiero y nutrir el modelo.*

- Cada `ConsolidatedSale` (estado `ACTIVE`) es visible en el panel financiero y alimenta las líneas de **VENTAS** del EFE. **No hay importación manual** (reemplaza la hoja `IMPORT_VENTAS`): la venta ya vive en el ERP.
- Mapeo venta → cuenta EFE por canal + tipo:
  - Ecommerce adquisición → `1.1.1.1`; Ecommerce recurrente (MRR) → `1.1.2.1`.
  - Kommo adquisición → `1.1.1.2`; Kommo MRR → `1.1.2.2`.
  - Ferias → `1.1.3`.
  - Flete → `1.2`; devoluciones/reembolsos (`04`, `state=REFUNDED`) → `1.3` en negativo.
  El criterio adquisición vs MRR se parametriza (por producto/pack o por marca de recurrencia).
- El valor que entra al EFE es el **neto** o el **bruto** según la línea (el modelo actual usa `Valor`); se respeta la convención del modelo y se documenta por línea.
- Un reembolso (`04 §5`) descuenta automáticamente de las líneas de ventas del mes correspondiente (coherente con "retirar la venta para no tener cifras ciegas").

---

## 5. Importación y clasificación de extractos bancarios

### 5.1 Importadores por banco (varios paneles de carga — requisito)

El módulo tiene **un panel de carga por banco/pasarela**: Bancolombia, MercadoPago, Bold, Nequi (extensible). Cada uno con su parser, porque cada extracto tiene formato propio.

**Bancolombia (formato plano confirmado)** — el CSV `000090190837…` tiene columnas sin encabezado:

| Col | Contenido | Uso |
|---|---|---|
| 1 | Nº de cuenta (`60100006016`) | banco |
| 2–3 | códigos internos | ignorar |
| 4 | Fecha `DDMMYYYY` (`17092025`) | parsear a fecha |
| 6 | **Valor** (con signo: + ingreso, − egreso) | monto + tipo |
| 7 | Código de transacción (`2142`, `4160`, `3339`…) | metadato |
| 8 | **Concepto** (`TRANSFERENCIA CTA SUC VIRTUAL`, `PAGO INTERBANCARIOS`, `IMPTO GOBIERNO 4X1000`, `COMPRA EN PAYU`) | concepto + auto-clasificación |

Lógica del parser (porta el `FORMATEADOR`): fecha `DDMMYYYY→date`; `tipo = 'EGRESO' if valor<0 else 'INGRESO'`; concepto de col 8; **dedup** por firma (banco+fecha+valor+concepto+ocurrencia) reproduciendo el `COUNTIFS` de "Verificación".

**MercadoPago / Bold / Nequi:** parsers análogos. Conceptos ya observados: MP `Approved payment` (ingreso), `Cargo por cobrar con Mercado Pago` (comisión, egreso); Bold `Venta de Seeds` con `REFERENCIA` alfanumérica. *Los formatos exactos de estos extractos deben aportarse para afinar el parser; el diseño ya contempla un importador por banco enchufable.*

### 5.2 `BankMovement` (modelo unificado)

```python
class BankMovement(BaseModel):
    bank             = FK(Bank)
    date             = DateField(db_index=True)
    value            = Decimal()                      # con signo
    item             = CharField()                    # INGRESO / EGRESO (derivado del signo)
    concept          = CharField()                    # concepto del extracto
    reference        = CharField(blank=True)          # p.ej. referencia Bold
    comment          = CharField(blank=True)
    # clasificación
    financial_account = FK(FinancialAccount, null=True)   # CUENTA EFE
    accounting_account= FK(AccountingAccount, null=True)   # CUENTA CONTABLE (PUC)
    attribution       = CharField(blank=True)
    is_interbank      = BooleanField(default=False)        # "Otros pasivos" (excluir de ingreso neto)
    # impuestos (opcional, del formateador)
    total_tax = Decimal(default=0); retefuente = Decimal(default=0)
    reteica = Decimal(default=0); reteiva = Decimal(default=0)
    # estado y trazabilidad
    status           = CharField(default='POR_CLASIFICAR')  # POR_CLASIFICAR/CLASIFICADO/CONCILIADO
    alegra_synced    = BooleanField(default=False)          # "REGISTRADO EN ALEGRA"
    alegra_id        = CharField(blank=True)
    import_batch     = FK('BankImportBatch', null=True)
    dedupe_hash      = CharField(db_index=True)             # anti-duplicado
    class Meta:
        constraints=[UniqueConstraint(fields=['bank','dedupe_hash'], name='uq_bankmov')]
```

### 5.3 Clasificación (el trabajo diario de contabilidad)

Requisito: dejar cada movimiento **listo para asignarle una cuenta del modelo financiero**.

- Pantalla tipo bandeja: movimientos `POR_CLASIFICAR` arriba; asignar `financial_account` (EFE), `accounting_account` (PUC) y `attribution`. Marcar `is_interbank` cuando sea transferencia entre cuentas propias.
- **Auto-clasificación por reglas** (`ClassificationRule`, parametrizable): match por banco + patrón de concepto → sugiere/asigna cuentas. Reduce el trabajo manual sobre conceptos repetitivos (intereses→rendimientos financieros, comisiones→gasto financiero, transferencias virtuales→canal de venta). El usuario confirma o corrige; las reglas aprenden de las correcciones (opcional).
- **Edición masiva**: seleccionar N movimientos con el mismo concepto → clasificar todos de una.
- **KPI de clasificación** (reemplaza `CONTROL DE CLASIFICACIÓN`): % de registros clasificados, y desglose ingresos/egresos, por mes. Meta operativa: 100%.
- Los movimientos clasificados alimentan el EFE (gastos/costos) y la auditoría (ingresos).

---

## 6. Modelo Financiero (EFE)

Estado mensual (columnas = meses; filas = cuentas EFE), calculado en vivo, no en fórmulas.

- **Líneas de ventas (1.x):** suma de `ConsolidatedSale` por cuenta EFE y mes (§4).
- **Líneas de gasto/costo (3.x, 5.x, 6.x, 7.x):** suma de las **cuotas mensuales** de los gastos documentados (`09_GASTOS`), por cuenta EFE y mes (entran en negativo). Cada gasto aporta una cuota por mes según su amortización: no amortizable → 1 cuota completa en su mes; amortizable a N meses → N cuotas iguales en meses consecutivos, calculadas automáticamente (`09 §5`). Estas líneas se nutren del pipeline de gastos con comprobante y factura, **no** directamente de los movimientos bancarios. Los `BankMovement` clasificados como egreso sirven para **conciliar** esos gastos (`09 §7`), no para imputar el EFE.
- **Líneas de recaudo (4.x):** ingresos reales clasificados (incluye rendimientos financieros, IVA generado, auditoría de ingresos).
- **Nodos padre:** suma de hijos (jerarquía por código).
- **Presupuesto (PPTO EFE):** columna de presupuesto por cuenta/mes, editable, para comparar real vs presupuesto.
- **Cierres de mes:** marcar un mes como cerrado (congela cifras, impide reimputación sin reapertura auditada).

Servicio `build_efe(year)` devuelve la matriz cuenta×mes (real, presupuesto, variación) lista para render. Cachear/materializar por desempeño; recalcular ante cambios de clasificación o ventas del mes.

Endpoints en `analytics`/`finance` para: EFE completo, drill-down de una línea (ver los movimientos/ventas que la componen), export a Excel con la misma forma que el modelo actual.

---

## 7. Auditoría de Ingresos (validación diaria — el gráfico de la foto)

Cruza, por **día y banco**, lo que el equipo reportó contra lo que realmente entró al banco. Reemplaza `SD VALIDACIÓN DIARIA DE CUENTAS`.

### 7.1 Las dos fuentes

**Ingresos según reportes** — lo que el equipo dice que entró, por día y cuenta (Efectivo Maji/Cami/Dani, Bancolombia Maji, Nequi Maji, Bancolombia Seeds, PayU, Mercadopago, Bold). Sale de las **ventas consolidadas** (por `payment_account`/cuenta bancaria y fecha) más los reportes de efectivo. Es la "verdad declarada".

**Ingresos según bancos** — lo que realmente entró, por día y banco, de `BankMovement` con `item=INGRESO`. Es la "verdad real".

### 7.2 El ajuste interbancario (clave)

Por banco se calcula además el **ingreso interbancario** = movimientos marcados `is_interbank` (clasificados como "Otros pasivos"). Y:

```
INGRESO NETO (banco, día) = INGRESOS del banco − INGRESOS INTERBANCARIOS del banco
```

Esto evita contar dos veces el dinero que solo se movió entre cuentas propias (p.ej. liquidación de MercadoPago hacia Bancolombia).

### 7.3 La validación

```
VALIDACIÓN (banco, día) = INGRESO NETO según bancos − INGRESO según reportes
```

- `≈ 0` → cuadra: lo reportado coincide con lo que entró.
- `> 0` → entró al banco más de lo reportado (falta registrar una venta/ingreso).
- `< 0` → se reportó más de lo que entró (pago que no llegó, incompleto, o recaudo en mes distinto → líneas `4.4.1/4.4.2/4.4.3` del EFE).

Tolerancia configurable (p.ej. ±$1.000 por redondeos de pasarela). Los descuadres fuera de tolerancia se resaltan y son accionables (abrir el detalle de movimientos y ventas de ese día/banco).

### 7.4 El gráfico

Gráfico de barras diarias por banco (Bancolombia, MercadoPago, Bold; extensible a Nequi/efectivo) mostrando la discrepancia `VALIDACIÓN` por día — idéntico en intención al de la imagen: barras a cero = cuadre perfecto, positivas/negativas = descuadre. Filtros por mes, banco, rango. Construido con el wrapper ECharts y la paleta Seeds (no el azul/magenta del ejemplo).

Además: tabla diaria banco×día con los tres bloques (reportes, bancos netos, validación) y totales de mes, exportable.

---

## 8. Conexión con Alegra (`04`)

`BankMovement` tiene `alegra_synced`/`alegra_id` (columna "REGISTRADO EN ALEGRA" del archivo actual): un egreso/ingreso clasificado puede registrarse como pago/gasto en Alegra. Fase 2, con la misma idempotencia y logging de `04`. Por ahora basta con el marcador y el id para conciliación.

---

## 9. API (borrador)

```
# Cuentas (parametrización)
GET/POST/PATCH/DELETE /api/v1/finance/accounts/efe/           # árbol EFE
GET/POST/PATCH/DELETE /api/v1/finance/accounts/puc/           # plan contable
GET/POST/PATCH        /api/v1/finance/banks/
GET/POST/PATCH        /api/v1/finance/classification-rules/

# Extractos bancarios
POST /api/v1/finance/bank-import/{bank}/        # subir CSV -> parse -> dry-run -> commit
GET  /api/v1/finance/movements/?status=&bank=&from=&to=       # bandeja, filtros por todas las columnas
PATCH/api/v1/finance/movements/{id}/            # clasificar
POST /api/v1/finance/movements/bulk-classify/   # clasificación masiva
GET  /api/v1/finance/classification/kpi/?month=

# Modelo financiero
GET  /api/v1/finance/efe/?year=                 # matriz cuenta x mes (real/ppto/var)
GET  /api/v1/finance/efe/line/{code}/drilldown/?month=
POST /api/v1/finance/efe/close-month/           # cierre de mes
GET  /api/v1/finance/efe/export/                # Excel

# Auditoría de ingresos
GET  /api/v1/finance/audit/reports-vs-banks/?month=&bank=      # tabla diaria
GET  /api/v1/finance/audit/chart/?month=                       # datos del gráfico de validación
```

---

## 10. Pantallas

- **Panel financiero (EFE):** matriz cuenta×mes, real vs presupuesto, drill-down por línea, cierre de mes, export. Vista de árbol colapsable.
- **Carga de extractos:** un panel por banco (Bancolombia, MercadoPago, Bold, Nequi) con subir → previsualizar (dry-run, duplicados detectados) → confirmar.
- **Clasificación:** bandeja de movimientos con auto-clasificación, edición masiva, KPI de % clasificado, filtro por todas las columnas.
- **Auditoría de ingresos:** el gráfico de validación diaria por banco + tabla reportes/bancos/validación + accesos al detalle de descuadres.
- **Configuración → Finanzas:** árbol de cuentas EFE, PUC, bancos, reglas de clasificación, mapeos de la validación, marcador interbancario.

Requisitos transversales (`00 §11`): filtro por todas las columnas, edición masiva, y Kanban donde aporte (bandeja de clasificación por estado). Estética Seeds.

---

## 11. Casos límite y recovery

| Caso | Manejo |
|---|---|
| CSV reimportado (mismas filas) | Dedup por `dedupe_hash` único por banco; no duplica. |
| Formato de extracto cambia | Parser versionado por banco; dry-run muestra filas no parseables sin abortar el lote. |
| Movimiento sin clasificar al cerrar mes | El cierre reporta el % sin clasificar y exige confirmación; quedan visibles como pendientes. |
| Transferencia interbancaria no marcada | Aparece como descuadre en la validación → señal para marcarla `is_interbank`. |
| Venta con `payment_account` que no mapea a un banco | Se lista en "reportes sin banco"; se corrige el mapeo en configuración. |
| Recaudo en mes distinto al de la venta | Líneas `4.4.x` de auditoría de ingresos lo absorben; no se pierde el cuadre anual. |
| Reembolso posterior | Descuenta ventas del mes y ajusta EFE y validación. |
| Doble registro en Alegra | Idempotencia por `alegra_id` (misma disciplina de `04`). |
| Cambio de árbol de cuentas con datos ya clasificados | Reasignación auditada; los movimientos guardan histórico de a qué cuenta estuvieron imputados. |

Toda importación deja `BankImportBatch` (archivo, filas, creadas, duplicadas, errores). Toda reclasificación deja `AuditLog`.