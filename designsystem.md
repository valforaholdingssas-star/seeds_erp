# Seeds Design System — v1.2 (Quiet Luxury Botánico)

Marca: **Seeds** — autocuidado, auriculoterapia, medicina china, ritual corporal.
Idea rectora: *Tu cuerpo, tu jardín.*

> Exportado como referencia portable del design system. Fuente completa en el proyecto: tokens CSS, componentes React, UI kits.

---

## 1. Color

Regla de proporción: Verdes 60–70% · Crema 20–30% · Vino 5–10% · Salvia/Arcilla/Rosa 3–8% combinados.

| Token | Hex | Rol |
|---|---|---|
| `--seeds-green-950` | `#0B1C11` | Verde Nocturno — overlays, footer, máxima profundidad |
| `--seeds-green-900` | `#112918` | Jardín Profundo — color madre, hero, nav |
| `--seeds-green-800` | `#1D2D1B` | Verde Sombra — cards oscuras |
| `--seeds-cream-100` | `#FDF9F0` | Crema Ritual — beige cálido, canvas editorial |
| `--seeds-wine-900` | `#5E0604` | Vino Profundo — acento premium, alta intención |
| `--seeds-terracotta-600` | `#93403A` | Arcilla Cuerpo — acento corporal secundario |
| `--seeds-sage-500` | `#62986C` | Salvia Botánica — línea ilustrativa |
| `--seeds-rose-300` | `#CA9697` | Rosa Arcilla — acento emocional limitado |

**Surfaces:** `--surface-cream #FDF9F0` · `--surface-warm-white #FFFEF8` · `--surface-dark #112918`

**Texto:** `--text-dark #112918` · `--text-dark-muted rgba(17,41,24,.68)` · `--text-dark-soft rgba(17,41,24,.46)` · `--text-on-dark #FDF9F0` · `--text-on-dark-muted rgba(253,249,240,.72)`

**Líneas:** `--line-on-light rgba(17,41,24,.14)` · `--line-on-dark rgba(253,249,240,.16)`

**Acentos semánticos:** `--accent-botanical` (sage) · `--accent-editorial` (terracotta) · `--accent-ritual` (wine) · `--accent-community` (rose)

---

## 2. Tipografía

Dos fuentes, contraste intencional: serif para atmósfera, sans para claridad.

- **Orpheus Pro** — serif de marca. Logo, hero, H1, manifiesto. Carga vía `@font-face` desde `frontend/public/fonts/` (woff2 licenciados). Fallback: Cormorant Garamond.
- **Ingra** — sans funcional. Body, nav, botones, forms. Misma carpeta `public/fonts/`. Fallback: Raleway.

`--font-serif: "Orpheus Pro", "Cormorant Garamond", Georgia, serif`
`--font-sans: "Ingra", "Raleway", Inter, Manrope, "Helvetica Neue", Arial, sans-serif`

| Token | Rol | Desktop | Peso | Line-height | Tracking |
|---|---|---|---|---|---|
| `--display-xl` | Hero institucional | 96–132px | 400 | 0.88–0.96 | -0.025em |
| `--display-lg` | H1 editorial | 72–88px | 400 | 0.95 | -0.02em |
| `--display-md` | H2 de sección | 48–56px | 400 | 1.05 | -0.01em |
| `--title-lg` | Producto / card grande | 34–40px | 400 | 1.10 | -0.005em |
| `--title-sm` | Subtítulo poético | 24–28px | 300 | 1.25 | 0 |
| `--body-lg` | Texto destacado | 19–21px | 300 | 1.60 | 0.01em |
| `--body-md` | Body principal | 16px | 300–400 | 1.65 | 0.01em |
| `--body-sm` | Texto secundario | 14px | 300–400 | 1.55 | 0.02em |
| `--label` | Labels UI (uppercase) | 11–12px | 400 | 1.20 | 0.14–0.18em |
| `--micro` | Disclaimer | 11px | 300 | 1.45 | 0.08em |

Reglas: sin negrillas pesadas · Orpheus siempre grande y con espacio · máximo un display serif + un body sans + un label sans por pantalla.

---

## 3. Espaciado, radios, contenedores

**Espaciado:** `--space-1` 4px → `--space-11` 160px (escala: 4,8,12,16,24,32,48,64,96,128,160)

**Radios:** `--radius-xs` 8px · `--radius-sm` 16px · `--radius-md` 24px · `--radius-lg` 32px · `--radius-xl` 40px · `--radius-pill` 999px · `--radius-circle` 50%

**Contenedores:** `--container-xs` 520px · `--container-sm` 680px · `--container-md` 960px · `--container-lg` 1180px · `--container-xl` 1366px

---

## 4. Sombras y movimiento

**Sombras** (la profundidad viene del color, no de sombras fuertes):
`--shadow-1: 0 4px 18px rgba(17,41,24,.05)` (cards suaves) · `--shadow-2: 0 18px 48px rgba(17,41,24,.10)` (modales) · `--shadow-3: 0 24px 64px rgba(11,28,17,.18)` (floating CTA)

**Movimiento** (respiración, nunca rebote):
`--duration-fast: 160ms` (hover/botones) · `--duration-base: 280ms` (cards/acordeones) · `--duration-slow: 520ms` (modales/hero)
`--ease-soft: cubic-bezier(.22,.61,.36,1)` · `--ease-ritual: cubic-bezier(.16,1,.30,1)`

Botón: `translateY(-1px)` hover, `scale(0.98)` press. Sin bounce, sin parallax de texto.

---

## 5. Componentes

| Componente | Variantes |
|---|---|
| Button | primary-dark, primary-wine, cream, outline, ghost |
| Card | cream, warm-white, dark, shadow |
| Badge | symptom, ritual, new, support, product, sage |
| Chip | default, sage, terracotta, wine, dark (idle/hover/selected) |
| Input | text/textarea, light/dark |
| Alert | info, caution, success, error |
| Nav | sticky, scroll-aware, light/dark |

Botones: pill (`radius-pill`), uppercase Ingra, min-height 44px. Cards: `radius 32–40px`, sin sombra externa por defecto.

---

## 6. Voz y copy

Guía calmada y experta, nunca vendedora. Siempre "tú". Sentence case en body; uppercase solo en labels.

**Usar:** "apoya", "acompaña", "puede ayudar a regular", "favorece una sensación de".
**Evitar:** "cura", "elimina", "garantiza", claims médicos absolutos, urgencia agresiva.

Ejemplos aprobados: *"Elige por dónde quieres empezar."* · *"Un ritual de 5 días para escuchar tu cuerpo."* · *"Descansa, observa y vuelve a sembrar."*

---

## 7. Iconografía

Sin sistema de iconos definido por la marca. Lenguaje visual: ilustración lineal botánica tipo grabado (pagodas, grullas, flores, semillas), sellos circulares como marcas gráficas, monograma `ee`. Glifos mínimos ✦ ◦ como separadores. Para iconos de UI funcional: librería thin-stroke (Lucide/Phosphor light), nunca sólidos.

---

## 8. Checklist quiet luxury

Una pieza pertenece a Seeds si cumple 6 de 8:
1. Verde Profundo/Nocturno es el ancla visual.
2. Crema Ritual aparece como pausa editorial.
3. Vino Profundo aparece poco y con intención.
4. Suficiente aire alrededor de texto/logo/producto.
5. Orpheus para marca, Ingra para función.
6. El patrón botánico no compite con el contenido.
7. Stickers/sellos se sienten premium, no cute.
8. El copy acompaña y guía, no presiona.

---

## Pendiente

- Subir archivos reales de Orpheus Pro (Light/Regular/Italic) e Ingra (Light/Regular/Medium) a `assets/fonts/` — actualmente usando fallbacks de Google Fonts.
- Fuente completa (tokens CSS, JSX de componentes, UI kits, assets) vive en el proyecto original — este .md es un resumen de referencia, no reemplaza los archivos fuente.
