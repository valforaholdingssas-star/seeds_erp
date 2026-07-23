# Seeds ERP — Paquete de Diseño (handoff a Claude Code / Codex)

Diseño del ERP de Seeds para reemplazar el stack **n8n + Google Sheets + Looker**.
Stack objetivo: **Backend** Python · Django · DRF · PostgreSQL + PostGIS · Celery/Redis · pgvector (RAG) · **Frontend** React 18 + TypeScript + Vite.

## Cómo usar este paquete
Leer en orden. `00` es obligatorio antes de cualquier código.

| Doc | Contenido |
|---|---|
| **00_ARQUITECTURA.md** | Stack, principios, estructura de proyecto, **Consolidado de Ventas (núcleo)**, ingesta recovery-first, integraciones, colas/throttling, Design System→UI, orden de construcción. |
| **01_VENTAS.md** | Vendedores, 4 canales (WooCommerce, Kommo, Ferias, Manuales), webhooks, normalización, plugin WordPress, import CSV/carga histórica, panel de métricas. |
| **02_LOGISTICA.md** | Envia (guías), espejos de dirección + formateo IA, generación masiva 1-a-1, contraste/warnings, Despachos. |
| **03_INVENTARIO.md** | Productos, Materiales, Kardex; descuento por pedido enviado. |
| **04_CONTABILIDAD.md** | Clientes↔Alegra, facturación **idempotente** (fiscal-crítica), reembolsos/notas crédito, IVA. |
| **05_USUARIOS_LEADS_RAG.md** | Usuarios/roles/permisos, Leads, capa de IA/RAG (tools + pgvector). |
| **06_FRONTEND.md** | **App React**: stack, shell de la interfaz, design system en código, `DataTable` con filtro por columna, edición masiva, Kanban drag&drop, consola de lotes en vivo, pantallas por módulo, panel de métricas. |
| **07_CONFIGURACION.md** | **Panel de configuración**: API keys y parámetros administrables desde la interfaz, cifrado de secretos, entornos sandbox/producción, probar conexión, auditoría de cambios. |

## Código implementado (monorepo)

| Ruta | Qué es |
|---|---|
| `backend/` | Django/DRF API |
| `frontend/` | React + Vite UI |
| `wordpress-plugin/seeds-erp-sync/` | Plugin WooCommerce → ERP (HMAC + cola) |
| `docker-compose.yml` | db · redis · api · worker · beat · web |

Login sandbox: `admin@seeds.co` / `admin1234` · UI http://localhost:5173 · API :8000

## Producción (EC2)

Ver guía completa: [`deploy/EC2.md`](deploy/EC2.md)

```bash
# En la EC2 (Ubuntu)
sudo bash deploy/bootstrap-ec2.sh
cp .env.production.example .env.production   # editar secretos + dominio
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## Flujo de datos (mapa mental)
```
WooCommerce ─webhook─┐
Kommo ──────webhook─┤
Ferias ─form interno┤─→ [Tabla origen por canal] ─normalización─→ ConsolidatedSale ─┬─→ Logística (guías Envia) ─→ Despachos ─→ Inventario (kardex OUT)
Manual ─form interno┘   (solo processing/completed)                                  ├─→ Contabilidad (factura Alegra, idempotente)
                                                                                     └─→ Métricas / RAG
```

## Mapeo hojas actuales → modelos nuevos
| Hoja `SD VENTAS 2026` | Modelo ERP |
|---|---|
| `N8N_ECOMMERCE` / `VENTAS ECOMMERCE` | `sales.EcommerceSale` |
| `N8N_KOMMO` / `VENTAS KOMMO` | `sales.KommoSale` |
| `N8N_VENTAS_MANUALES` / `VENTAS MANUALES` | `sales.ManualSale` (+ FeriaSale) |
| `CONSOLIDADO VENTAS` | `sales.ConsolidatedSale` + `SaleItem` |
| `GUÍAS` / `N8N_GUIAS` | `logistics.Shipment` (tracking_number, Costo→shipping_cost) |
| `GUÍAS FALLIDAS` / `N8N_GUIAS_FALLIDAS` | `Shipment.status=GUIA_FALLIDA` |
| `REPORTING_LOGISTICS` / `Sheet16` (pivots) | `analytics` (endpoints agregados) |
| `ERROR NOTIFICATION` / `N8N_ERORR_FLOW` | `integrations.IntegrationLog` / `RawWebhookEvent(FAILED)` |

## Hechos clave extraídos de las fuentes (no perder en implementación)
- **Solo `processing`/`completed`** entran al consolidado. `pending/cancelled/failed/error` se quedan en origen.
- **Dorados/Plateados** con multiplicador de pack (WooCommerce `product_id 602 → ×3`, color por `meta_data key=pa_color`). Parametrizable en `ProductPackRule`.
- **Cédula WooCommerce**: leer por `key` en `meta_data`, NO por índice fijo (`meta_data[2]` es frágil).
- **Kommo**: body form-encoded → GET lead (`?with=contacts`) → GET contacto; vendedor = campo `Comercial`; `status` inicial `processing`.
- **Envia**: `POST /ship/generate/`, Bearer token, origen fijo Seeds, `city`=código DANE, `state`=ISO, carrier `coordinadora`/`ground`, label PDF `STOCK_4X6`. Respuesta → nº guía + `Costo`. **Una a una** (rate limit).
- **Formateo IA**: ciudad→depto/código (fallback difuso+LLM), dirección→prefijos `cll/cra/tv/dg`; guarda "no enviar" ante ".", "Domicilio", "Recoger", vacío.
- **Alegra**: Basic Auth (email+token), `/contacts` (guarda `alegra_id`), `/invoices`. **Idempotencia fiscal estricta**: nunca doble emisión; reconciliar antes de reintentar.
- **Reembolso**: nota crédito Alegra + retirar venta del consolidado + reversa de inventario + bandeja "anular factura".
- **Configuración**: ninguna credencial en código ni en variables de entorno. Todo (tokens Envia/Alegra/Woo/Kommo/IA, origen de envío, metas de ventas, IVA, multiplicadores, columna ganada de Kommo) se administra desde el panel, cifrado en base de datos. Solo 4 variables quedan en el entorno: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `SEEDS_SECRETS_KEY`.

## Requisitos transversales de UX (todos los módulos)
1. Filtrado por **todas** las columnas. 2. Vistas **Kanban drag&drop** donde aporte. 3. **Edición masiva**.
Se resuelven con tres componentes genéricos de React (`DataTable`, `KanbanBoard`, `BulkEditBar`) reutilizados por todos los módulos — ver `06_FRONTEND §5`.
UI **debe** cumplir el Seeds Design System (verde profundo/crema/vino, Orpheus+Ingra, pill buttons, sombras suaves, movimiento sin bounce). Nivel Monday/Zoho en fluidez. Sin librerías con identidad propia (MUI/Ant): headless + Tailwind con tokens Seeds.

## Verificaciones pendientes antes de codear integraciones
- Esquema exacto y vigente de Alegra `contacts`/`invoices`/`credit-notes` en `https://developer.alegra.com/`.
- Campos exactos de la respuesta de Envia `ship/generate` (nombres de nº de guía, costo, ciudad generada) contra `https://docs.envia.com/`.
- IDs de columna/pipeline de Kommo que representan "venta ganada" (parametrizar, no hardcodear).
