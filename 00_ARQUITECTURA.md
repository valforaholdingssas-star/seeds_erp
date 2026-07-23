# Seeds ERP — 00 · Arquitectura del Sistema

> Documento maestro de diseño. Punto de entrada para Claude Code / Codex.
> Los módulos se detallan en documentos separados (`01_VENTAS`, `02_LOGISTICA`, `03_INVENTARIO`, `04_CONTABILIDAD`, `05_USUARIOS_Y_RAG`).
> **Regla de oro para el agente de desarrollo:** leer este documento completo antes de escribir código. La estructura de datos del *Consolidado de Ventas* (§7) es el corazón del sistema; todo lo demás gira alrededor.

---

## 1. Objetivo

Reemplazar el stack actual **n8n + Google Sheets + Looker Studio** por un ERP propio, en Python/Django, que:

- Centralice las **ventas** de 4 canales (Ecommerce/WooCommerce, Kommo, Ferias, Manuales) en una sola base consolidada, en tiempo real y con recovery robusto.
- Gestione **logística y envíos** vía API de Envia (generación de guías, formateo de direcciones con IA, despachos).
- Controle **inventario** (productos, materiales, kardex) descontando por pedido enviado.
- Maneje **contabilidad** (clientes, facturación electrónica vía Alegra, reembolsos, IVA) con idempotencia fiscal estricta.
- Capture **leads**.
- Exponga una capa de **IA con RAG sobre la base de datos** para operaciones asistidas (formateo, consultas, automatizaciones comerciales).

El sistema hoy vive parcialmente en el archivo `SD VENTAS 2026` (Google Sheets) con hojas crudas (`N8N_*`), hojas de transformación (`VENTAS *`) y una hoja `CONSOLIDADO VENTAS`. El ERP reproduce esa canalización pero como base de datos relacional normalizada, no como fórmulas de hoja de cálculo.

### 1.1 Alcance de esta fase

Orden de construcción recomendado (ver §12): **Usuarios/Vendedores → Ventas → Logística → Inventario → Contabilidad → Leads**. El RAG se integra transversalmente una vez existan datos.

---

## 2. Stack tecnológico

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.12+ |
| Framework | Django 5.x + Django REST Framework |
| Base de datos | PostgreSQL 16 + **PostGIS** (ver §2.1) |
| Async / colas | Celery 5 + Redis (broker + result backend) |
| Programación periódica | Celery Beat (actualización de estados de órdenes, reintentos) |
| Auth | JWT (email + password), `djangorestframework-simplejwt` |
| Realtime (opcional fase 2) | Django Channels + Redis (para el tablero de generación de guías en vivo) |
| IA / RAG | `pgvector` (extensión Postgres) + orquestador LLM (ver `05_USUARIOS_Y_RAG`) |
| Documentación API | `drf-spectacular` (OpenAPI 3) |
| Frontend | **SPA en React 18 + TypeScript + Vite**, consumiendo la API. Debe cumplir el **Seeds Design System**. Especificación completa en `06_FRONTEND` (§11 es el resumen) |
| Infra | Docker + docker-compose (api, worker, beat, postgres+postgis, redis) |
| Observabilidad | Logs estructurados JSON + tabla de auditoría + `IntegrationLog` (§9) |

### 2.1 ¿PostGIS sí o no?

**Sí, recomendado**, pero de uso acotado. Justificación: el punto más frágil del sistema actual es que *las direcciones y ciudades llegan mal* y las guías se generan a destinos equivocados. PostGIS permite:

- Normalizar ciudad/departamento contra un catálogo geográfico oficial (**códigos DANE** de municipio y **códigos ISO** de departamento) con búsqueda difusa + geometría.
- Guardar el punto geocodificado de la dirección validada para contrastar contra la ciudad de la guía generada por Envia.

Si se prefiere no adoptar PostGIS en la primera iteración, se puede empezar con `pg_trgm` (búsqueda difusa por trigramas) sobre un catálogo `GeoCatalog` de municipios y migrar a PostGIS después. **Decisión por defecto: habilitar PostGIS + pg_trgm desde el inicio** (habilitar ambas extensiones no tiene costo relevante).

---

## 3. Principios de diseño

1. **Domain-first / services + selectors.** Cada app tiene `models.py`, `selectors/` (lecturas), `services/` (escrituras con reglas de negocio y side-effects), `serializers.py`, `views.py`, `urls.py`, `tasks.py` (Celery). Las vistas nunca contienen lógica de negocio: llaman a servicios/selectores. (Mismo patrón del backend de referencia adjunto.)
2. **Idempotencia en todo lo que toca sistemas externos.** Webhooks entrantes, generación de guías y facturación deben ser idempotentes por clave natural (`order_id`/`lead_id`/`sale_id`) para no duplicar guías ni **—crítico—** facturas ante la DIAN.
3. **Nada se pierde (recovery-first).** Todo evento externo se persiste crudo *antes* de procesarse (`RawWebhookEvent`, §8). Si el procesamiento falla, el evento queda reintentable. Ningún fallo de un paso posterior puede descartar el dato original.
4. **Estados explícitos (máquinas de estado).** Órdenes, guías y facturas tienen estados finitos y transiciones auditadas, no booleanos sueltos.
5. **Separación fuente ↔ consolidado.** Cada canal escribe primero en su tabla de origen (espejo de las hojas `N8N_*` / `VENTAS *`); un único servicio de normalización promueve a `ConsolidatedSale`. Reproduce la canalización de las hojas, pero con transformaciones en Python y no en fórmulas.
6. **Solo ventas válidas en el consolidado.** Únicamente `processing` y `completed` llegan a `ConsolidatedSale`. `pending`, `cancelled`, `failed`, `error` se quedan en la tabla de origen con su estado. (Ver §7.3.)
7. **Auditoría obligatoria** en toda acción sensible (creación/edición de venta, generación de guía, emisión de factura, reembolso, cambios de rol).

---

## 4. Estructura del proyecto

```
seeds-erp/
├── app/
│   ├── settings/{base,local,production,logging}.py
│   ├── celery.py
│   ├── urls.py  asgi.py  wsgi.py
├── apps/
│   ├── common/          # constants, exceptions, pagination, mixins, base models (UUID+timestamps)
│   ├── config/          # SettingValue + registro de parámetros, cifrado de secretos, panel de configuración
│   ├── audit/           # AuditLog + servicio log_audit_event
│   ├── integrations/    # RawWebhookEvent, IntegrationLog, clientes HTTP (Envia, Alegra, WooCommerce, Kommo), rate limiter
│   ├── geo/             # GeoCatalog (municipios DANE / departamentos ISO), PostGIS, servicios de normalización + IA de direcciones
│   ├── users/           # User (roles), permisos
│   ├── sellers/         # Vendedor (parametrizable, con o sin usuario)
│   ├── sales/           # ConsolidatedSale + tablas de origen por canal + webhooks + import CSV + métricas
│   ├── logistics/       # Shipment/Guía (Envia), Despachos
│   ├── inventory/       # Product, Material, Kardex (movimientos)
│   ├── accounting/      # Customer (Alegra), Invoice, Refund/NotaCredito, IVA
│   ├── leads/           # Lead
│   └── analytics/       # endpoints de métricas / paneles
├── manage.py  requirements.txt  .env.example  Dockerfile  docker-compose.yml
```

Cada app bajo `apps/` sigue el layout `selectors/ services/ tasks.py`. `integrations/` y `geo/` son transversales.

---

## 5. Modelo de datos base (mixins)

Todos los modelos de negocio heredan de un abstracto común:

```python
# apps/common/models.py
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True
```

Convenciones:
- **PK = UUID** en todo lo interno. Los IDs externos (`order_id` de WooCommerce, `lead_id` de Kommo) se guardan como campos indexados *adicionales*, nunca como PK.
- Dinero: `DecimalField(max_digits=14, decimal_places=2)`. Nunca float. (Las hojas usan floats; en el ERP se corrige.)
- Timestamps en UTC; zona de presentación `America/Bogota`.
- Índices en toda columna por la que el usuario filtra (requisito: *filtrado por todas las columnas* en todos los módulos).

---

## 6. Usuarios, roles y permisos (resumen — detalle en `05`)

Modelo `User` con auth email+password+JWT (igual al backend de referencia). Roles (TextChoices):

| Rol | Descripción |
|---|---|
| `ADMIN` | Acceso total, configuración, parametrización. |
| `VENTAS` | Gestiona ventas, ve su desempeño; edición según pertenencia. |
| `LOGISTICA` | Guías, despachos, inventario de salida. |
| `CONTABILIDAD` | Clientes, facturas, reembolsos, IVA. |
| `SUPERVISOR` | Lectura amplia + métricas. |
| `VIEWER` | Solo lectura. |

Permisos por objeto donde aplique (ej.: un vendedor ve sus ventas; ADMIN ve todo). El **Vendedor** (`sellers.Vendedor`) es una entidad distinta del `User`: un vendedor puede tener un usuario asociado o no (caso `ECOMMERCE`, `FERIAS`, que no son personas). Ver `01_VENTAS §2`.

---

## 7. El Consolidado de Ventas (núcleo del sistema)

Es la tabla `sales.ConsolidatedSale`. Reproduce la hoja `CONSOLIDADO VENTAS` pero normalizada. **Toda venta válida de cualquier canal termina aquí**, y de aquí se alimentan logística, contabilidad e inventario.

### 7.1 Estructura de datos objetivo (la que pidió el negocio)

Campos mínimos que el negocio exige por venta consolidada:

| Campo negocio | Campo modelo | Notas |
|---|---|---|
| ID de la orden / lead | `external_id` + `source` | Clave natural única por canal (ver 7.4) |
| Monto pagado x producto | `amount_products` | Decimal |
| Monto pagado x envío | `amount_shipping` | Decimal (en Ecommerce viene del transporte; en Kommo suele ser 0) |
| Nombre del cliente | `customer_name` | |
| Dirección | `address_raw` | Cruda como llega |
| Teléfono | `phone` | |
| Correo electrónico | `email` | |
| Ciudad | `city_raw` | Cruda |
| Municipio o departamento | `state_raw` | Cruda |
| Cédula de ciudadanía | `id_number` | |
| Producto(s) y cantidad(es) | `items` (relación) | Ver 7.2 |

Campos adicionales heredados de la operación actual (mapeados 1:1 de las hojas):
`closed_at` (Fecha de cierre), `deal_name` (Nombre del negocio), `total_value` (Valor), `stage` (Etapa del negocio), `payment_account` (Cuenta bancaria: Mercadopago, Bancolombia Seeds, Tarjeta (Bold), Nequi, Efectivo…), `income_source` (E-COMMERCE/KOMMO/FERIAS), `status` (§7.3), `commercial` (→ FK a Vendedor), `iva_generated`, `net_value`, `net_value_plus_shipping`, `symptoms` (Síntoma/s), `order_notes`, `age` (Edad).

### 7.2 Productos y cantidades — modelo Dorados/Plateados

Seeds vende kits en dos líneas de color: **Dorados** y **Plateados**, cada uno con un "tipo". El consolidado guarda por venta: `cantidad_dorados`, `cantidad_plateados`, `tipo_dorados`, `tipo_plateados`. Para el nuevo ERP esto se modela como líneas de venta:

```
ConsolidatedSale (1) ──< SaleItem (N)
SaleItem: product (FK inventory.Product), color {DORADO|PLATEADO}, tipo, quantity
```

**Lógica de cantidad (crítica, viene del código n8n de WooCommerce):** ciertos productos son *packs con multiplicador*. Ej.: `product_id 602` = "Refill automático trimestral (3 kits cada 3 meses)" ⇒ multiplicador **×3**. El color se lee del `meta_data` del line item con `key == 'pa_color'` (valores `dorado(s)`/`plateado(s)`). `unidades_reales = quantity × multiplicador`. El multiplicador debe ser **parametrizable en el módulo de productos** (tabla `ProductPackRule`), no hardcodeado. Fallback por nombre si cambia el `product_id` (contiene "3 kits").

### 7.3 Estados de la orden (`status`) y regla de consolidación

Valores observados en datos reales: `processing`, `completed`, `pending`, `failed`, `cancelled`, `error`, y etapas Kommo tipo `Cierre ganado`.

**Regla dura:** `ConsolidatedSale` **solo** contiene ventas con `status ∈ {processing, completed}`. El resto vive en la tabla de origen del canal. Cuando WooCommerce actualiza una orden (webhook de order-update):
- `pending → processing/completed`: se **promueve** al consolidado.
- `processing/completed → cancelled/failed/refunded`: se **retira** del consolidado (soft-delete / estado `WITHDRAWN`) y se descuenta de métricas (ver reembolsos, `04`).

Máquina de estados de `ConsolidatedSale`:
```
DRAFT → ACTIVE → (WITHDRAWN | REFUNDED)
```
`ACTIVE` = visible en tablas de ventas y elegible para logística/facturación.

### 7.4 Clave natural / anti-duplicados

`unique_together = (source, external_id)` donde `source ∈ {ECOMMERCE, KOMMO, FERIAS, MANUAL}`. Esto reemplaza la columna "CONTROL DUPLICADOS" (`COUNTIF`) de las hojas. Todo upsert de webhook usa esta clave.

### 7.5 Cálculos fiscales (heredados de las fórmulas de la hoja)

- IVA Colombia 19%. De la hoja: `IVA_GENERADO = max(0, (Valor − Transporte) − (Valor − Transporte)/1.19)`.
- `VALOR_AL_NETO_DE_IMPUESTOS = Valor − IVA_generado`.
- `amount_shipping` (Transporte): en Ecommerce se obtiene del costo real de la guía (hoja `GUÍAS`, columna `Costo`) una vez generada; en Kommo por defecto 0. Debe recalcularse cuando llega el costo de Envia.

Estos cálculos se implementan en `services`, no en el modelo, y se recalculan ante cambios de valor o transporte.

---

## 8. Ingesta de eventos externos (recovery-first)

Toda entrada externa (webhooks de WooCommerce/Kommo, respuestas de Envia/Alegra) pasa por `integrations`:

```
RawWebhookEvent
  id, source {WOOCOMMERCE|KOMMO|...}, event_type, received_at,
  headers (JSON), payload (JSON crudo), signature,
  status {RECEIVED|PROCESSED|FAILED|IGNORED}, error, attempts, processed_at,
  dedupe_key (índice único: p.ej. "woo:order:4428:processing")
```

Flujo estándar de webhook:
1. La vista recibe el POST, **valida firma**, persiste `RawWebhookEvent(status=RECEIVED)` y responde `200` de inmediato (ack rápido; evita reintentos del emisor y timeouts).
2. Un task Celery (`process_raw_event`) toma el evento, ejecuta el pipeline del canal (parseo → upsert origen → normalización → consolidado), marca `PROCESSED`.
3. Si falla: `FAILED` + `error` + backoff exponencial (reintentos automáticos, N configurable). Panel de "eventos fallidos" con botón *reprocesar* manual.
4. `dedupe_key` evita procesar dos veces el mismo evento (idempotencia).

`IntegrationLog` registra cada llamada saliente (Envia/Alegra): request, response, status_code, latencia, resultado — base de auditoría y de los flujos de reintento.

---

## 9. Integraciones externas (contratos resumidos)

| Sistema | Uso | Auth | Endpoint base | Detalle |
|---|---|---|---|---|
| WooCommerce (WordPress) | Alta y actualización de órdenes ecommerce | Webhook firmado + REST API (consumer key/secret) o plugin propio | `/wp-json/wc/v3/` | `01_VENTAS §4` |
| Kommo (CRM) | Alta de venta al mover lead de columna | Webhook + OAuth2 (long-lived token) | `https://<subdominio>.kommo.com/api/v4/` | `01_VENTAS §5` |
| Envia.com | Generación de guías | **Bearer token** (sandbox y producción con tokens/URLs distintos) | `https://api.envia.com/ship/generate/` | `02_LOGISTICA` |
| Alegra | Contactos + facturación electrónica DIAN | **HTTP Basic** (email + token) | `https://api.alegra.com/api/v1/` | `04_CONTABILIDAD` |
| LLM (OpenAI u otro) | Formateo de direcciones, RAG | API key | — | `02` y `05` |

> Rate limiting: Envia y Alegra deben llamarse **una a una** (secuencial, con throttle) en operaciones masivas, para no ser bloqueados. Se implementa un rate limiter central en `integrations` (token-bucket sobre Redis) usado por los tasks de generación de guías y facturación (ver §10).

> **Credenciales:** ninguna de estas integraciones lleva sus tokens en código ni en variables de entorno. Todas se administran desde el panel de configuración (`07_CONFIGURACION`), incluyendo el cambio entre sandbox y producción.

---

## 10. Colas, throttling y operaciones masivas

Patrón para "seleccionar N registros y ejecutar acción externa a cada uno" (generar guías / emitir facturas):

- El endpoint crea un `BatchJob` (id, tipo, total, creado_por) y encola **una subtarea Celery por ítem**, encadenadas o con un rate limiter que garantice **1 request cada X ms** al proveedor.
- Cada subtarea: llama al proveedor, persiste resultado en `IntegrationLog`, actualiza el estado del registro (guía OK / guía fallida / factura generada / factura fallida) y **publica progreso** (Channels o polling) para que la tabla del módulo se actualice "a medida que van llegando" las respuestas.
- Reintentos por ítem con backoff; el `BatchJob` nunca falla en bloque: cada ítem es independiente.
- Configurable: concurrencia = 1 para Envia/Alegra (secuencial), tamaño de lote, delay entre requests.

---

## 11. Design System → implementación de UI

> El frontend es una **SPA en React + TypeScript**; su arquitectura, librerías, estructura de carpetas y pantallas están especificadas en **`06_FRONTEND`**. Esta sección es solo la traducción del design system a reglas de UI.

El frontend **debe** cumplir el *Seeds Design System v1.2 (Quiet Luxury Botánico)*. Traducción operativa para el desarrollador:

- **Estética objetivo:** al nivel de Monday/Zoho/Notion en fluidez y profesionalismo, pero con la identidad Seeds (no un theme genérico). Moderno, con aire, editorial.
- **Tokens CSS** (exportar como variables `:root`, tomadas del design system):
  - Verdes ancla: `--seeds-green-900 #112918` (nav/hero), `--seeds-green-950 #0B1C11` (overlays/footer), `--seeds-green-800 #1D2D1B` (cards oscuras).
  - Superficies: `--surface-cream #FDF9F0`, `--surface-warm-white #FFFEF8`, `--surface-dark #112918`.
  - Acentos: vino `#5E0604` (premium, poco), terracota `#93403A`, salvia `#62986C`, rosa `#CA9697`.
  - Semánticos de estado del ERP: éxito→salvia, warning→terracota/arcilla, error→vino, info→verde. (Reusar la paleta, no introducir colores nuevos tipo azul/amarillo de dashboards.)
  - Proporción de color: verdes 60–70%, crema 20–30%, vino 5–10%, otros 3–8%.
- **Tipografía:** serif de marca **Orpheus Pro** (fallback Cormorant Garamond) para títulos/hero; sans **Ingra** (fallback Raleway/Inter) para UI, body, botones, tablas. Labels en uppercase con tracking amplio. Máx. 1 display serif + 1 body sans + 1 label por pantalla.
- **Radios:** cards 24–40px; botones pill (`999px`), min-height 44px, uppercase Ingra.
- **Sombras suaves** (`0 4px 18px rgba(17,41,24,.05)`); la profundidad viene del color, no de sombras duras.
- **Movimiento:** transiciones 160/280/520ms, easing `cubic-bezier(.22,.61,.36,1)`; hover `translateY(-1px)`, press `scale(.98)`. Sin bounce ni parallax.
- **Voz/copy** en la UI: calmada, en "tú", sentence case. Usar "apoya/acompaña"; evitar claims agresivos.
- **Iconografía:** thin-stroke (Lucide/Phosphor light), nunca sólidos. Ilustración botánica lineal como acento, sin competir con datos.
- **Componentes base** a construir en la librería: Button (primary-dark, primary-wine, cream, outline, ghost), Card (cream/warm-white/dark), Badge (symptom/ritual/new/support/product/sage), Chip, Input (light/dark), Alert (info/caution/success/error), Nav sticky, **DataTable** (con filtro por columna, edición masiva, selección múltiple), **Kanban** (drag&drop), **charts** (ver métricas en `01_VENTAS §9`).

Requisitos transversales de UX (aplican a TODOS los módulos):
1. **Filtrado por todas las columnas** en cada tabla.
2. **Vistas Kanban con drag & drop** donde aporte (estados de pedidos, guías, despachos, facturas, leads).
3. **Edición masiva** (seleccionar N filas → editar campo / ejecutar acción).

---

## 12. Orden de construcción para el agente de desarrollo

1. **Fundaciones:** proyecto Django, settings, Docker (postgres+postgis, redis), `common`, `audit`, **`config`** (registro de parámetros + secretos cifrados — se necesita antes que cualquier integración), `integrations` (RawWebhookEvent, IntegrationLog, rate limiter), `users` (auth JWT + roles), `geo` (GeoCatalog + PostGIS).
2. **`sellers`** (Vendedor parametrizable).
3. **`sales`** (`01_VENTAS`): modelos consolidado + origen por canal; servicio de normalización; webhooks Ecommerce y Kommo; formularios internos Ferias/Manuales; import CSV / carga de datos históricos de `SD VENTAS 2026`; métricas.
4. **`logistics`** (`02_LOGISTICA`): Envia, formateo de direcciones (IA + catálogo), generación masiva de guías, contraste/warnings, Despachos.
5. **`inventory`** (`03_INVENTARIO`): Product/Material/Kardex; descuento por pedido enviado.
6. **`accounting`** (`04_CONTABILIDAD`): Customer↔Alegra, Invoice, Refund/NotaCrédito, IVA; generación masiva.
7. **`leads`**.
8. **RAG** (`05`): pgvector, ingestión, endpoints de IA.

**Frontend en paralelo** (`06_FRONTEND`): el shell de la aplicación + la librería de componentes del design system + el `DataTable` genérico se construyen junto con el paso 1, porque todos los módulos dependen de ellos. Luego cada módulo entrega backend y pantallas juntos.

Cada paso entrega API + tests + seed de datos + pantallas React.

---

## 13. Seguridad y cumplimiento

- JWT access corto (15 min) + refresh; permisos cerrados por defecto (`IsAuthenticated`).
- **Secretos administrados desde el panel de configuración** (`07_CONFIGURACION`), cifrados en base de datos con AES-GCM. Solo cuatro variables viven en el entorno: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL` y la llave maestra `SEEDS_SECRETS_KEY`. Ningún secreto se serializa hacia el frontend ni aparece en logs (scrubbing obligatorio).
- Auditoría obligatoria en acciones sensibles.
- **Fiscal (crítico):** la emisión de facturas a la DIAN es irreversible; idempotencia y control de doble emisión son requisito de seguridad, no solo de negocio (ver `04`).
- Validación de firma en webhooks entrantes.
- Rate limiting en login y en llamadas salientes.
