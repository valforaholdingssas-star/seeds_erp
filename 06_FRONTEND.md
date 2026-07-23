# Seeds ERP — 06 · Frontend (React)

> Requiere `00_ARQUITECTURA` (§11 Design System→UI) y los módulos `01`–`05` para el detalle de endpoints y estados.
> Aplicación **React** que consume la API DRF. Repositorio separado (`seeds-erp-web`) o monorepo con `/backend` y `/frontend`.

---

## 1. Stack

| Necesidad | Elección | Por qué |
|---|---|---|
| Base | **React 18 + TypeScript + Vite** | TS es obligatorio: el dominio (estados de guía, factura, venta) es demasiado sensible para tipos implícitos. Vite por velocidad de dev. |
| Routing | **React Router v6** (rutas por módulo, guards por rol) | Maduro, anidado, con `loader`/`lazy` para code-splitting por módulo. |
| Estado servidor | **TanStack Query** | Todo el estado del ERP es estado de servidor: cache, invalidación, refetch, polling de batch jobs, optimistic updates en edición masiva. |
| Estado UI local | **Zustand** (mínimo) | Solo para filtros persistentes, vista activa, selección de filas. Sin Redux. |
| Tablas | **TanStack Table v8** (headless) + virtualización (`@tanstack/react-virtual`) | Requisito de *filtrado por todas las columnas* + edición masiva + miles de filas. Headless = se estiliza 100% con el DS de Seeds. |
| Kanban / drag&drop | **dnd-kit** | Accesible (teclado), performante, sin el peso de react-beautiful-dnd (descontinuado). |
| Gráficas | **Apache ECharts** (vía `echarts-for-react`) | El panel reemplaza a Looker: series comparativas año-vs-año, barras por día de semana, pies/treemaps por ciudad. ECharts tematiza bien a la paleta Seeds y aguanta densidad. *(Alternativa más simple si se prefiere: Recharts.)* |
| Formularios | **react-hook-form + zod** | Validación tipada compartida con los contratos de la API (ferias, ventas manuales, direcciones). |
| Estilos | **Tailwind CSS** con tokens Seeds en `tailwind.config` + CSS variables | Rapidez sin arrastrar una identidad ajena. |
| Primitivas UI | **Radix UI** (headless) | Diálogos, dropdowns, tooltips, tabs accesibles **sin estilos propios**. |
| Fechas / dinero | `date-fns` + `date-fns-tz` (`America/Bogota`), `Intl.NumberFormat('es-CO', COP)` | El negocio opera en COP y zona Bogotá. |
| Realtime | **WebSocket** (Django Channels) con fallback a polling de TanStack Query | Progreso en vivo de generación de guías y facturación masiva. |
| Tests | Vitest + Testing Library; **Playwright** para E2E | E2E obligatorio en los flujos críticos (guías y facturación). |

> **Decisión deliberada: no usar MUI, Ant Design ni Chakra.** Traen una identidad visual fuerte que habría que pelear en cada componente para cumplir el Seeds Design System. Headless (Radix + TanStack + Tailwind) permite que el DS sea la única fuente de verdad estética.

---

## 2. Concepto de interfaz

**Trabajo:** un operador de Seeds pasa el día en tablas densas — revisando ventas, corrigiendo direcciones, generando guías, emitiendo facturas. La interfaz tiene que ser rápida y silenciosa, no decorativa.

**Estructura (shell del ERP):**

```
┌──────────┬────────────────────────────────────────────────┐
│          │  breadcrumb / título de sección    [acciones]  │  ← barra superior clara
│  SIDEBAR ├────────────────────────────────────────────────┤
│  verde   │                                                │
│ profundo │   CANVAS CREMA                                 │
│ #112918  │   tabla / kanban / panel de métricas           │
│          │                                                │
│  módulos │   (filtros arriba, contenido virtualizado)     │
│          │                                                │
│  ee      │                                                │
└──────────┴────────────────────────────────────────────────┘
```

- **Sidebar** en Jardín Profundo (`--seeds-green-900`), fija, con el monograma `ee` arriba y los módulos en Ingra uppercase con tracking amplio. Es el ancla verde de toda la aplicación.
- **Canvas** en Crema Ritual (`--surface-cream #FDF9F0`) — el área de trabajo respira, no es gris corporativo.
- **Vino Profundo** (`#5E0604`) reservado para lo irreversible: emitir factura, anular, eliminar. Si el usuario ve vino, algo tiene consecuencias fiscales o de dinero. Esa disciplina cromática *es* la señalización del sistema.

> **Nota sobre la proporción del DS:** la regla original (verdes 60–70%) está pensada para piezas editoriales de marca. En una herramienta de datos densos se adapta: el verde vive en el sidebar, encabezados, estados activos y gráficas; el crema domina el área de trabajo. La identidad se mantiene por tipografía, color de acento, radios y movimiento. Dejarlo explícito para que no se lea como un incumplimiento del DS.

**Elemento característico:** la **consola de progreso de lote**. Cuando se generan 40 guías o 30 facturas, el sistema las procesa una a una (requisito de rate limit) y la pantalla lo muestra: una lista donde cada fila se resuelve en vivo — pendiente → en curso → guía `76116174690` / error con motivo. Convierte una limitación técnica en la parte más informativa de la interfaz. Ver §6.

---

## 3. Design System en código

### 3.1 Tokens
Un único `src/styles/tokens.css` con las variables del DS (colores, superficies, texto, líneas, radios, sombras, duraciones, easings), consumidas por `tailwind.config.ts`:

```ts
// tailwind.config.ts (extracto)
colors: {
  green: { 950:'#0B1C11', 900:'#112918', 800:'#1D2D1B' },
  cream: { 100:'#FDF9F0' },
  wine:  { 900:'#5E0604' },
  terracotta: { 600:'#93403A' },
  sage:  { 500:'#62986C' },
  rose:  { 300:'#CA9697' },
},
borderRadius: { xs:'8px', sm:'16px', md:'24px', lg:'32px', xl:'40px', pill:'999px' },
fontFamily: {
  serif: ['"Orpheus Pro"','"Cormorant Garamond"','Georgia','serif'],
  sans:  ['Ingra','Raleway','Inter','system-ui','sans-serif'],
},
transitionDuration: { fast:'160ms', base:'280ms', slow:'520ms' },
```

Escala tipográfica del DS (`display-xl` … `micro`) como utilidades. Espaciado 4→160px según la escala del DS.

⚠️ **Pendiente heredado del DS:** faltan los archivos reales de **Orpheus Pro** e **Ingra**; hoy se usan fallbacks de Google Fonts. Montar los `@font-face` con `font-display: swap` desde `assets/fonts/` en cuanto estén, sin tocar el resto del código (los tokens ya apuntan ahí).

### 3.2 Semántica de estado
Los estados del ERP se mapean a la paleta existente — **no se introducen colores nuevos**:

| Estado | Color | Uso |
|---|---|---|
| Éxito / listo | Salvia `#62986C` | Guía generada, factura generada, enviado |
| Advertencia / revisar | Arcilla `#93403A` | Destino distinto al pedido, stock bajo, vendedor sin resolver |
| Error / irreversible | Vino `#5E0604` | Guía fallida, factura fallida, anular, reembolso |
| Neutro / en proceso | Verdes + crema | Por generar, en curso |

### 3.3 Inventario de componentes
Construir en `src/components/ui/` siguiendo §5 del DS: `Button` (primary-dark, primary-wine, cream, outline, ghost — pill, min-height 44px, uppercase Ingra), `Card` (cream/warm-white/dark), `Badge`, `Chip`, `Input`/`Textarea`/`Select` (light/dark), `Alert` (info/caution/success/error), `Nav`, `Modal`, `Drawer`, `Toast`, `Tabs`, `DatePicker`/`DateRangePicker`.

Movimiento: `160ms` hover, `280ms` cards/acordeones, `520ms` modales; easing `cubic-bezier(.22,.61,.36,1)`. Hover `translateY(-1px)`, press `scale(.98)`. **Sin bounce, sin parallax.** Respetar `prefers-reduced-motion`.

---

## 4. Estructura del proyecto

```
frontend/src/
├── app/            # router, providers (QueryClient, auth, theme), layout shell
├── components/
│   ├── ui/         # design system (Button, Card, Badge, Input, Alert…)
│   ├── data/       # DataTable, ColumnFilter, BulkEditBar, SavedViews, ExportButton
│   ├── kanban/     # KanbanBoard, KanbanColumn, KanbanCard (dnd-kit)
│   ├── charts/     # ECharts wrapper + tema Seeds + gráficas del panel
│   └── batch/      # BatchConsole (progreso en vivo)
├── features/
│   ├── auth/  sales/  sellers/  logistics/  dispatch/
│   ├── inventory/  accounting/  leads/  analytics/  settings/
│   └── (cada uno: api.ts · hooks.ts · schemas.ts · components/ · pages/)
├── lib/            # apiClient (axios + interceptores JWT), formatters, permissions, ws
├── styles/         # tokens.css, fonts.css, tailwind.css
└── types/          # tipos generados desde OpenAPI (drf-spectacular)
```

**Tipos desde el backend:** generar el cliente/tipos con `openapi-typescript` a partir del schema de `drf-spectacular`. Evita que el frontend y el backend se desincronicen en los estados críticos (`GUIA_FALLIDA`, `FACTURA_GENERADA`, etc.).

---

## 5. Patrones transversales (los tres requisitos del negocio)

### 5.1 `DataTable` — filtrado por todas las columnas
Componente único reutilizado por todos los módulos, configurado por columnas:

- **Filtro por columna** según tipo: texto (contiene/igual), número (rango), fecha (rango), enum (multi-select), booleano. Los filtros se serializan a query params y se envían al backend (filtrado server-side, nunca en cliente sobre datos paginados).
- Ordenamiento multi-columna, paginación server-side, virtualización de filas.
- **Selección múltiple** (checkbox + shift-click + "seleccionar todo lo filtrado").
- **Visibilidad y orden de columnas** configurable, persistido por usuario.
- **Vistas guardadas** ("Pedidos por generar guía de Bogotá") — combinación de filtros + columnas, con nombre.
- Exportar a CSV lo filtrado.
- Estados vacíos con dirección, no decorativos: *"No hay pedidos por generar guía. Los pedidos aparecen aquí cuando una venta se confirma."*

### 5.2 Edición masiva
Al seleccionar filas aparece una **barra de acciones inferior** (no un modal que tape la tabla): `N seleccionados · [Editar campo] [Acción del módulo] [Limpiar]`.
- Editar campo: elegir columna → nuevo valor → previsualización de cuántos registros cambian → confirmar.
- Optimistic update con rollback si el backend rechaza; toast con resultado (`N actualizados, M con error` + detalle).
- Edición inline por celda donde tenga sentido (espejos de dirección y ciudad en logística).

### 5.3 Kanban con drag & drop
`KanbanBoard` genérico sobre dnd-kit, alimentado por el mismo endpoint que la tabla (mismos filtros):
- **Ventas:** por `state` / etapa.
- **Logística:** `POR_GENERAR → GUIA_FALLIDA → LISTO_PARA_ENVIAR → ENVIADO`.
- **Despachos:** `LISTO_PARA_ENVIAR → ENVIADO`.
- **Facturación:** `POR_GENERAR → ENVIANDO → GENERADA / FALLIDA`.
- **Leads:** `NUEVO → CONTACTADO → CALIFICADO → CONVERTIDO / DESCARTADO`.

Reglas: las transiciones inválidas se rechazan visualmente **antes** de soltar (la columna destino no acepta el drop) según la máquina de estados del backend; drag con teclado; toda transición confirma contra la API y revierte si falla. Mover a un estado con efectos externos (emitir factura) **no** se dispara por drag: abre confirmación explícita.

---

## 6. Operaciones por lote con progreso en vivo (`BatchConsole`)

Aplica a *generar guías* (`02`) y *emitir facturas* (`04`), que se procesan **una a una** por rate limit.

Flujo de interfaz:
1. Selección en tabla → `[Generar guías]` → modal de confirmación con resumen (cuántos, cuáles no cumplen requisitos y por qué).
2. `POST` de lote → devuelve `batch_id` → se abre la **consola de progreso** (panel lateral persistente, se puede minimizar y seguir trabajando).
3. Suscripción WebSocket al `batch_id` (fallback: polling cada 2s). Cada ítem pasa por `pendiente → en curso → resuelto`:
   - ✅ éxito: número de guía / número de factura, con enlace al PDF.
   - ⛔ error: motivo textual del proveedor + botón **Reintentar** individual.
4. Al terminar: resumen (`38 generadas · 2 fallidas`) y acción **Reintentar fallidas**.
5. La tabla de fondo se actualiza fila a fila conforme llegan los resultados (invalidación selectiva de la query).

**Salvaguarda en facturación:** el botón de emitir se deshabilita mientras hay un envío en curso para esa factura (`ENVIANDO`), y los reintentos exigen pasar por la reconciliación descrita en `04 §4.6`. La interfaz nunca ofrece "reintentar" a secas sobre una factura cuyo estado en Alegra no se ha verificado — un doble envío tiene consecuencias ante la DIAN.

---

## 7. Pantallas por módulo

| Módulo | Pantallas |
|---|---|
| **Auth** | Login, recuperar contraseña, perfil propio. |
| **Ventas** | Consolidado (tabla + kanban), detalle de venta, formulario Ferias, formulario Manual, importador CSV (subir → mapear columnas → dry-run con reporte → confirmar), reconciliación Ecommerce por rango de fechas, eventos fallidos (con reprocesar). |
| **Vendedores** | CRUD, alias, activo/inactivo, vínculo opcional con usuario. |
| **Métricas** | Panel global + por canal + por comercial (§8). |
| **Logística** | Tablero de envíos (espejos editables, botón formatear con IA por fila y en lote, warnings visibles), generación de guías por lote, detalle de envío con respuesta cruda del proveedor. |
| **Despachos** | Vista de bodega: solo guía + dorados/plateados; marcar enviado (individual/masivo); pestaña de enviados. |
| **Inventario** | Productos, Materiales, Kardex (solo lectura, filtrable), entradas/ajustes, alertas de stock bajo. |
| **Contabilidad** | Clientes (+ estado de sincronización con Alegra), Facturas (tabla + kanban, emitir, emitir en lote, reintentar, ver PDF), Reembolsos (bandeja "anular factura" pendiente), IVA por período. |
| **Leads** | Kanban + tabla + detalle. |
| **Configuración** | Integraciones (credenciales enmascaradas, probar conexión, entorno sandbox/producción), parámetros de negocio (metas de ventas, IVA, multiplicadores de packs, columna ganada de Kommo, origen y dimensiones de envío), usuarios y roles, catálogo geográfico, historial de cambios. Detalle en `07_CONFIGURACION §5`. |

---

## 8. Panel de métricas (reemplazo de Looker)

Debe contener como mínimo lo del tablero actual (`01_VENTAS §9`). Componentes de gráfica a construir sobre el wrapper ECharts con tema Seeds:

- `KpiCard` — Meta, Ventas del período, Performance %, Proyección, Venta diaria esperada, Venta a la fecha, VDE en unidades. Cada uno con delta vs período anterior (▲/▼ en salvia/vino).
- `WeekdayBars` — ventas por día de la semana (mes actual e histórico).
- `DailyLine` — ventas diarias vs venta diaria esperada vs promedio.
- `YearComparisonLine` — año actual vs anterior por mes.
- `CityBreakdown` — ventas por ciudad (histórico y mes), pie o treemap.

Estructura: pestañas **Global · Por canal · Por comercial**, con filtros persistentes (rango de fechas, canal, vendedor, ciudad, estado) en la barra superior. Cada vista consume los endpoints de `analytics`.

**Tema de gráficas:** paleta Seeds (verdes, salvia, terracota, vino, rosa) sobre crema — nada del azul/magenta genérico del Looker actual. Ejes y grillas con `--line-on-light`, etiquetas en Ingra `--body-sm`, sin sombras ni degradados.

---

## 9. Auth, permisos y seguridad en cliente

- Login → `access` (memoria) + `refresh` (httpOnly cookie si el backend lo permite; si no, storage con expiración corta). Interceptor axios: refresh silencioso en 401 con cola de reintentos.
- **Guards por ruta y por rol** (`ADMIN`, `VENTAS`, `LOGISTICA`, `CONTABILIDAD`, `SUPERVISOR`, `VIEWER`), derivados de la matriz de `05 §1`.
- Los permisos del cliente son **UX, no seguridad**: el backend valida siempre. Se ocultan acciones que el rol no puede ejecutar en lugar de mostrar errores.
- Sesión expirada → redirección con retorno a la ruta previa, sin perder el trabajo en formularios (borrador local).
- **Secretos:** el frontend nunca recibe una credencial. Los campos de API key son de solo escritura y muestran máscara (`••••4821`) más metadatos. El acceso a la sección de credenciales exige **re-autenticación**, y el entorno activo (sandbox/producción) se muestra de forma permanente en la aplicación. Ver `07_CONFIGURACION §3 y §5`.

---

## 10. Calidad

- **Rendimiento:** code-splitting por módulo; virtualización en tablas; `staleTime` afinado por tipo de dato (métricas 5 min, tablas operativas 30 s, batch en vivo por WS); paginación server-side siempre.
- **Accesibilidad:** foco visible, navegación por teclado completa (incluido kanban), roles ARIA vía Radix, contraste AA sobre crema y sobre verde, `prefers-reduced-motion`.
- **Responsive:** el ERP es de escritorio, pero Despachos debe funcionar en tablet/móvil (bodega): vista de tarjetas en lugar de tabla, acciones grandes.
- **Copy:** español, en "tú", sentence case, verbos activos. El botón dice lo que pasa ("Generar guías" → toast "Guías generadas"). Los errores explican qué pasó y cómo seguir, sin disculpas ni vaguedades.
- **Tests:** unitarios de formatters y máquinas de estado; integración de DataTable (filtros, selección, edición masiva); **E2E Playwright** de los dos flujos críticos: generar guías por lote (con fallos simulados y reintento) y emitir factura (incluyendo el guard de doble emisión).
- **Build/deploy:** Vite build → estáticos servidos por nginx en su propio contenedor; variables por entorno (`VITE_API_URL`, `VITE_WS_URL`); añadir el servicio `web` al `docker-compose`.
