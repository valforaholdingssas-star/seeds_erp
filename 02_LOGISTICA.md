# Seeds ERP — 02 · Módulo de Logística y Envíos

> Requiere `00_ARQUITECTURA` (§8 ingesta, §9 integraciones, §10 operaciones masivas) y `01_VENTAS` (Consolidado).
> App: `apps/logistics` + `apps/geo`. Integración: **Envia.com** (`https://api.envia.com/ship/generate/`, Bearer token, sandbox y producción con tokens/URLs distintos).

Dos submódulos: **Envíos/Guías** (genera guías desde el consolidado) y **Despachos** (lo que ve el equipo de bodega). El problema central a resolver: *las direcciones/ciudades llegan mal y las guías se crean a destinos equivocados.* Por eso el módulo tiene columnas espejo editables, formateo con IA, y contraste automático entre lo pedido y lo que Envia generó.

---

## 1. Modelos

```python
class Shipment(BaseModel):
    sale              = OneToOne(sales.ConsolidatedSale, related_name='shipment')
    # --- espejos editables de la dirección real (requisito) ---
    address_mirror    = CharField(blank=True)   # espejo editable de sale.address_raw
    city_mirror       = CharField(blank=True)   # espejo editable de sale.city_raw
    state_mirror      = CharField(blank=True)   # depto/municipio editable
    # --- normalización geo ---
    geo_city          = FK(geo.GeoCatalog, null=True)   # municipio resuelto (código DANE)
    geo_state_code    = CharField(blank=True)           # ISO depto (p.ej. "DC")
    address_formatted = CharField(blank=True)           # salida IA (cll/cra/tv/dg…)
    # --- guía Envia ---
    status            = CharField(choices=ShipmentStatus, default='POR_GENERAR')
    carrier           = CharField(default='coordinadora')
    service           = CharField(default='ground')
    tracking_number   = CharField(blank=True, db_index=True)  # "número de guía"
    label_url         = URLField(blank=True)                  # PDF STOCK_4X6
    shipping_cost     = Decimal(null=True)                    # "Costo" que devuelve Envia
    # --- destino tal como Envia lo generó (para contraste) ---
    generated_city    = CharField(blank=True)
    generated_state   = CharField(blank=True)
    generated_address = CharField(blank=True)
    warning           = BooleanField(default=False)           # destino generado != destino pedido
    warning_detail    = JSONField(default=dict)
    # --- error / recovery ---
    last_error        = TextField(blank=True)
    attempts          = IntegerField(default=0)
    envia_shipment_id = CharField(blank=True)                 # id interno de Envia (idempotencia)

class DispatchStatus:  # submódulo Despachos
    LISTO_PARA_ENVIAR = 'LISTO_PARA_ENVIAR'
    ENVIADO           = 'ENVIADO'
```

### 1.1 Máquina de estados de `Shipment`
```
POR_GENERAR ──generar guía OK──> LISTO_PARA_ENVIAR ──despacho──> ENVIADO
     │
     └──error Envia──> GUIA_FALLIDA ──reintentar──> (POR_GENERAR)
```
Estados: `POR_GENERAR`, `GUIA_FALLIDA`, `LISTO_PARA_ENVIAR`, `ENVIADO`. (El status del pedido en la tabla se deriva de aquí, como pediste: "por generar guía / guía fallida / listo para enviar".)

---

## 2. `geo.GeoCatalog` y normalización de destino

Catálogo oficial de Colombia para resolver ciudad→(código DANE municipio + código ISO departamento), que es lo que Envia exige (`city` numérico tipo `11001000`, `state` tipo `DC`).

```python
class GeoCatalog(BaseModel):
    municipality      = CharField(db_index=True)   # "Bogotá"
    municipality_code = CharField()                # DANE, "11001000"
    department        = CharField()                # "Bogotá D.C."
    department_iso    = CharField()                # "DC"
    point             = PointField(null=True)      # PostGIS (opcional)
    search            = CharField()                # normalizado sin tildes, lower (pg_trgm)
```
Poblarse una vez con el catálogo DANE. Búsqueda: exacta → difusa (pg_trgm/PostGIS) → IA (fallback).

### 2.1 Formateo con IA (portar los AI Agents de n8n)

Tres funciones de IA, con el catálogo como primera línea y el LLM como fallback (exactamente como el flujo Kommo, pero encapsulado en `geo/services/ai_format.py`):

1. **Ciudad → departamento + código.** Si la coincidencia exacta con `GeoCatalog` falla, un prompt LLM infiere el municipio colombiano más probable (por similitud fonética/ortográfica) y devuelve `city_code, department_ISO`. **Guardas de seguridad:** si el campo viene vacío, es sólo un punto, o dice "Domicilio"/"Recoger"/etc. → responder señal de "no enviar" y marcar el shipment como *no despachar / revisar* (no generar guía).
2. **Formateo de dirección.** Normaliza a convención colombiana para que la plataforma de envíos la acepte sin errores de digitación: `calle→cll`, `carrera→cra`, `transversal→tv`, `diagonal→dg`, etc. Salida → `address_formatted`.
3. **(Opcional, Bogotá) Clasificador de zona.** norte/sur/oriente/occidente/centro… (usado hoy para lógica de guía; mantener como metadato).

Prompts base (heredados del workflow, en español, "no expliques tu razonamiento, no devuelvas más de una opción, sin puntuación").

### 2.2 Botón "formatear con IA" por fila (requisito)
Cada fila del módulo de envíos tiene un botón que dispara el formateo IA sobre `address_mirror`/`city_mirror` y rellena `address_formatted`/`geo_*`. También en lote (seleccionar N → formatear). El usuario puede editar manualmente los espejos antes o después.

---

## 3. Tablero de Envíos (pantalla principal)

Muestra **todos los pedidos del consolidado que requieren envío** (solo ventas `ACTIVE`; en Ecommerce solo processing/completed — nunca las no exitosas). Columnas mínimas:

`external_id (id pedido) · nombre · dirección real (sale.address_raw) · dirección espejo (editable) · ciudad real · ciudad espejo (editable) · depto · status · [botón formatear IA] · número de guía · costo guía · destino generado (ciudad/depto/dir) · warning · error/respuesta`

Requisitos UX (de `00 §11`): filtro por todas las columnas, selección múltiple, edición masiva de los espejos, y **vista Kanban** por estado (POR_GENERAR / GUIA_FALLIDA / LISTO_PARA_ENVIAR / ENVIADO) con drag&drop.

---

## 4. Generación de guías (Envia) — masiva, una a una

Requisito: seleccionar uno o varios pedidos y generar guías masivamente, **pero enviando la solicitud una a una** (secuencial) para no ser bloqueados por rate limit, mostrando resultados a medida que llegan.

### 4.1 Payload a Envia (`POST /ship/generate/`, confirmado del workflow)

```jsonc
{
  "origin": {                        // FIJO (parametrizable en settings del módulo)
    "name": "<external_id> - Seeds", "company": "Seeds",
    "email": "seeds.atencion@gmail.com", "phone_code": "CO", "phone": "3507047110",
    "street": "Ak 7 #155C-30", "number": "North Point Torre E Oficina 1502",
    "city": "11001000", "state": "DC", "country": "CO",
    "identification": "901908375", "type": "origin"
  },
  "destination": {                   // desde el shipment (espejos + geo + IA)
    "name": "<customer_name>", "company": "<external_id>",
    "email": "<email>", "phone": "<phone>", "country": "CO",
    "street": "<address_formatted>", "number": "",
    "city": "<geo_city.municipality_code>",   // DANE
    "state": "<geo_state_code>",              // ISO
    "identification": "<id_number>"
  },
  "packages": [{
    "content": "Seeds paquetes x1", "amount": 1, "type": "box",
    "dimensions": {"length":18,"width":12,"height":5},
    "weight": 0.1, "weightUnit": "KG", "lengthUnit": "CM",
    "declaredValue": 45000, "insurance": 45000
  }],
  "shipment": { "carrier": "coordinadora", "service": "ground", "type": 1 },
  "settings": { "printFormat": "PDF", "printSize": "STOCK_4X6",
                "comments": "Guía creada automáticamente - Cliente <contact_id>" }
}
```
Header: `Authorization: Bearer <ENVIA_TOKEN>`. Origen, dimensiones, peso, valor declarado y carrier/service deben ser **parámetros de configuración**, no constantes en código. El número de paquetes / dimensiones podría depender de cantidades (fase 2).

### 4.2 Orquestación (usar patrón `BatchJob` de `00 §10`)
1. Usuario selecciona N pedidos → `POST /api/v1/logistics/shipments/generate/ {ids}`.
2. Se crea `BatchJob`; se encola **una subtarea por pedido, secuencial**, con rate limiter (1 request cada X ms; concurrencia = 1).
3. Cada subtarea:
   - Valida destino (geo resuelto, dirección formateada, no marcado "no enviar"). Si falta → `GUIA_FALLIDA` con motivo, sin llamar a Envia.
   - Llama a Envia; registra en `IntegrationLog`.
   - **Éxito:** guarda `tracking_number`, `shipping_cost` (Costo), `label_url`, `generated_city/state/address`; ejecuta contraste (§5); estado → `LISTO_PARA_ENVIAR`. Actualiza `sale.amount_shipping` con el costo real y recalcula IVA/neto (Ecommerce).
   - **Error:** estado → `GUIA_FALLIDA`, guarda `last_error` (respuesta del endpoint), `attempts += 1`; queda con botón *reintentar*.
   - Publica progreso (Channels/polling) → la tabla se va llenando "a medida que llegan" las guías o los errores.
4. Idempotencia: no regenerar guía si el shipment ya tiene `tracking_number` (evita doble guía y doble costo). Reintentar solo desde `GUIA_FALLIDA`.

### 4.3 Respuesta de Envia
Extraer del response: número de guía (`tracking_number`), costo (`Costo`), url del label PDF, y ciudad/depto/dirección efectivamente usados por el carrier (para contraste). Guardar el response crudo en `IntegrationLog`.

---

## 5. Contraste destino pedido ↔ destino generado (warnings)

Requisito clave: al llegar la guía, el sistema compara automáticamente la ciudad/depto/dirección **con las que se generó la guía** contra las columnas de destino del pedido. Si difieren → `warning=True` + estado/indicador de warning en la fila, para verificar que la guía se generó al destino correcto.

Lógica: normalizar ambos lados (sin tildes, lower, via `geo`) y comparar municipio y departamento (y opcionalmente similitud de dirección con umbral). Registrar el detalle en `warning_detail` (`{campo: {pedido, generado}}`). El warning **no** bloquea el despacho, pero lo resalta para revisión humana.

---

## 6. Submódulo Despachos (bodega)

Pantalla separada para logística de bodega. Solo ve pedidos en `LISTO_PARA_ENVIAR`. Muestra **únicamente lo que bodega necesita** (como en el Excel): `número de guía` + configuración de empaque = `cantidad_dorados` (Seeds Dorados) + `cantidad_plateados` (Seeds Plateados) [+ tipos]. No datos comerciales ni de cliente.

Acciones:
- Marcar `ENVIADO` (individual o masivo). Al pasar a `ENVIADO`:
  - Desaparece de la pantalla activa de despachos.
  - **Dispara el descuento de inventario** (ver `03`) según productos y cantidades.
  - Deja registro/fecha de envío.
- Sección "Pedidos enviados": vista/tab dentro de la pantalla para consultar históricos (`ENVIADO`), con filtros por todas las columnas.

Vista Kanban recomendada: columnas `LISTO_PARA_ENVIAR → ENVIADO` con drag&drop; edición masiva de estado.

---

## 7. API (borrador)

```
GET   /api/v1/logistics/shipments/                 # tablero envíos, filtros por todas las columnas
PATCH /api/v1/logistics/shipments/{id}/            # editar espejos (address/city/state)
POST  /api/v1/logistics/shipments/bulk-update/     # edición masiva de espejos
POST  /api/v1/logistics/shipments/{id}/format-ai/  # formatear dirección/ciudad con IA
POST  /api/v1/logistics/shipments/format-ai/       # formateo en lote
POST  /api/v1/logistics/shipments/generate/        # generar guías (batch, secuencial) {ids:[]}
POST  /api/v1/logistics/shipments/{id}/retry/      # reintentar guía fallida
GET   /api/v1/logistics/batches/{id}/              # progreso del BatchJob

# Despachos
GET   /api/v1/logistics/dispatch/                  # solo LISTO_PARA_ENVIAR
POST  /api/v1/logistics/dispatch/mark-sent/        # {ids:[]} -> ENVIADO (+ descuenta inventario)
GET   /api/v1/logistics/dispatch/sent/             # históricos ENVIADO
```

---

## 8. Casos límite y recovery

| Caso | Manejo |
|---|---|
| Ciudad/dir vacía, ".", "Domicilio", "Recoger" | IA devuelve "no enviar"; shipment marcado revisar; no se llama a Envia. |
| Ciudad no está en catálogo | pg_trgm/PostGIS difuso → IA fallback; si sigue sin resolver, `GUIA_FALLIDA` con motivo "ciudad no resuelta". |
| Envia devuelve error / timeout | `GUIA_FALLIDA` + `last_error`; reintento manual y/o automático con backoff; nunca se pierde el pedido. |
| Rate limit del endpoint | Envío secuencial 1-a-1 con throttle (token-bucket Redis); concurrencia 1. |
| Guía ya generada (doble click / reintento) | Idempotencia por `tracking_number`/`envia_shipment_id`; no regenerar. |
| Guía a destino equivocado | Contraste §5 → `warning`; revisión humana antes de despachar. |
| Costo de guía no llega | `shipping_cost` null; recálculo de IVA queda pendiente; tarea de reconciliación. |
| Pedido pasa a ENVIADO sin guía | Bloqueado por máquina de estados (solo desde LISTO_PARA_ENVIAR). |
| Cancelación de guía | (Fase 2) endpoint Envia de cancelación; estado revertido + nota. |

Toda llamada a Envia queda en `IntegrationLog`; toda acción de estado en `AuditLog`.
