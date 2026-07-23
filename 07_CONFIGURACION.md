# Seeds ERP — 07 · Módulo de Configuración y Secretos

> Requiere `00_ARQUITECTURA` (§9 integraciones, §13 seguridad). App: `apps/config`.
> Objetivo: **toda variable de operación — API keys, tokens, URLs, parámetros de negocio — se administra desde un panel dentro del ERP**, sin tocar código ni redeploy.

---

## 1. Principio y su única excepción

Todo parámetro configurable vive en base de datos y se edita desde el panel. **Excepción inevitable: la llave maestra de cifrado y las credenciales de la propia base de datos deben venir del entorno.**

La razón es de arranque: si los secretos se guardan cifrados en la base, la llave que los descifra no puede estar guardada en la misma base (sería como dejar la llave dentro de la caja fuerte). Y para leer la base primero hay que poder conectarse a ella.

Por lo tanto:

| Vive en el entorno (`.env` / secrets manager) | Vive en el panel (base de datos, cifrado) |
|---|---|
| `DJANGO_SECRET_KEY` | Token de Envia (sandbox y producción) |
| `DATABASE_URL` | Credenciales de Alegra (email + token) |
| `REDIS_URL` | Consumer key/secret y secreto HMAC de WooCommerce |
| **`SEEDS_SECRETS_KEY`** (llave maestra de cifrado) | Credenciales y subdominio de Kommo |
| | API key y modelo del proveedor de IA |
| | Todos los parámetros de negocio (§4) |

Son cuatro variables de entorno en total. Todo lo demás se administra desde la interfaz.

---

## 2. Modelo de datos

### 2.1 Registro de parámetros (declarado en código)

Los parámetros se **declaran en código** (nombre, tipo, categoría, si es secreto, valor por defecto, validación) y sus **valores viven en base de datos**. Así el panel se construye solo a partir del registro, y agregar un parámetro nuevo no requiere migración ni tocar el frontend.

```python
# apps/config/registry.py
SETTINGS = [
    Setting(key='envia.token_prod', label='Token de producción', group='ENVIA',
            type=SECRET, required=True, help='Se obtiene en el panel de Envia → Developers'),
    Setting(key='envia.environment', label='Entorno', group='ENVIA',
            type=CHOICE, choices=['sandbox','production'], default='sandbox'),
    Setting(key='envia.request_delay_ms', label='Espera entre solicitudes', group='ENVIA',
            type=INT, default=1200, help='Milisegundos entre guías. Subirlo si el proveedor bloquea.'),
    ...
]
```

```python
class SettingValue(BaseModel):
    key            = CharField(unique=True, db_index=True)
    value          = TextField(blank=True)        # valores no secretos, en claro
    encrypted      = BinaryField(null=True)       # valores secretos, cifrados
    is_secret      = BooleanField(default=False)
    version        = IntegerField(default=1)
    updated_by     = FK(users.User, null=True)
    updated_at     = DateTimeField(auto_now=True)

class SettingAudit(BaseModel):          # historial: qué cambió, quién, cuándo — NUNCA el valor
    key, actor (FK User), action {CREATED|UPDATED|ROTATED|DELETED},
    old_value_masked, new_value_masked,   # solo máscara para no-secretos; vacío para secretos
    ip_address, created_at
```

### 2.2 Cifrado de secretos

- Cifrado autenticado **AES-GCM** (o `Fernet` de `cryptography`) con la llave maestra `SEEDS_SECRETS_KEY`.
- Se cifra al guardar, se descifra solo al momento de usarse en una llamada saliente.
- El valor descifrado **nunca** se serializa hacia el frontend, ni se escribe en logs, ni viaja en mensajes de error.
- Opcional para producción madura: envelope encryption con un KMS (AWS/GCP), reemplazando la llave local sin cambiar el resto del diseño.

### 2.3 Precedencia de valores

```
valor en panel (BD)  >  variable de entorno  >  valor por defecto del registro
```

Esto permite arrancar el sistema con variables de entorno (bootstrap / CI / pruebas) y migrar al panel sin fricción. El panel muestra de dónde viene cada valor efectivo.

---

## 3. Acceso al panel y reglas de seguridad

- Solo rol **`ADMIN`**. Se recomienda un permiso dedicado `can_manage_config` para poder delegar sin dar admin completo.
- **Re-autenticación (step-up)** para ver o editar la sección de credenciales: pedir la contraseña de nuevo aunque haya sesión activa. Sesión de configuración con expiración corta.
- **Los secretos son de solo escritura.** La API nunca devuelve el valor:
  - `GET` devuelve máscara + metadatos: `{key, masked: "••••4821", is_set: true, updated_at, updated_by}`.
  - `PATCH` acepta el valor nuevo; enviar vacío significa "no cambiar", no "borrar".
- **Auditoría obligatoria** de todo cambio (`SettingAudit` + `AuditLog`): quién, cuándo, desde qué IP, qué clave. Nunca el valor.
- **Scrubbing:** filtrar claves sensibles en logs, trazas y reportes de errores (Sentry `before_send`), y en `IntegrationLog` (guardar request/response con los headers de autorización redactados).
- **Rotación:** al guardar una credencial nueva se incrementa `version`; opcionalmente se retiene la anterior unos minutos para no romper tareas en vuelo.

---

## 4. Qué se configura (inventario completo)

### 4.1 Envia (logística)
`environment` (sandbox/producción) · token sandbox · token producción · URL base por entorno · carrier por defecto (`coordinadora`) · servicio (`ground`) · **datos de origen de Seeds** (nombre, empresa, NIT, email, teléfono, calle, complemento, ciudad DANE, departamento ISO) · dimensiones por defecto (18×12×5 cm) · peso (0.1 kg) · valor declarado y seguro (45.000) · formato y tamaño de etiqueta (PDF, STOCK_4X6) · espera entre solicitudes (ms) · reintentos y backoff.

### 4.2 Alegra (contabilidad)
`environment` · email de la cuenta · token API · URL base · numeración/resolución de facturación · impuesto por defecto (IVA 19%) · forma de pago por defecto · espera entre solicitudes · reintentos · **interruptor de facturación masiva** (kill switch).

### 4.3 WooCommerce (ecommerce)
URL de la tienda · consumer key · consumer secret · **secreto HMAC del webhook** · clave del campo de cédula en `meta_data` (evita depender del índice) · estados que se consideran venta válida (`processing`, `completed`) · mapeo de pasarela → cuenta bancaria.

### 4.4 Kommo (CRM)
Subdominio · client id / client secret / token de larga duración · **pipeline y columna que significan "venta ganada"** (selector, no valor fijo en código) · mapeo de nombres de campos personalizados (`# Seeds Dorados`, `Dirección entrega`, `Comercial`, …) por si Kommo los renombra.

### 4.5 Inteligencia artificial
Proveedor · API key · modelo para formateo de direcciones · modelo para RAG · temperatura · límite de tokens · **interruptor general de IA** · prompts editables (ciudad→departamento, formateo de dirección, clasificador de zona) con versionado.

### 4.6 Parámetros de negocio (no secretos, igual de importantes)
- **Ventas:** porcentaje de IVA · estados que entran al consolidado · multiplicadores de packs (`602 → ×3`) · alias de vendedores.
- **Metas comerciales:** meta de ventas por período, global y por vendedor — alimentan los KPIs de performance y proyección del panel de métricas (`01 §9`).
- **Inventario:** umbrales de stock bajo · si el stock negativo bloquea o solo advierte.
- **Sistema:** zona horaria (`America/Bogota`) · moneda (COP) · retención de logs y eventos crudos.

---

## 5. Panel de configuración (interfaz)

Pantalla en `features/settings/` con navegación por secciones: **Integraciones · Negocio · Usuarios y roles · Sistema**.

Cada tarjeta de integración muestra:

```
┌──────────────────────────────────────────────────────────┐
│  ENVIA                            ● Conectado · sandbox  │
│                                                          │
│  Token de producción    ••••••••4821   Actualizado 12 jul│
│  Token de sandbox       ••••••••9f02   por Daniel        │
│  Entorno                [ sandbox ▾ ]                    │
│  Espera entre guías     [ 1200 ] ms                      │
│                                                          │
│  [ Probar conexión ]                    [ Guardar ]      │
└──────────────────────────────────────────────────────────┘
```

Elementos obligatorios:

- **Indicador de estado** por integración: conectado / sin credenciales / error de autenticación / última llamada correcta.
- **Botón "Probar conexión"** que hace una llamada real de solo lectura al proveedor y reporta el resultado sin guardar nada. Debe existir *antes* de poder activar una credencial nueva.
- **Distintivo de entorno visible y permanente.** Si Alegra o Envia están en sandbox, una franja lo indica en toda la aplicación; si están en producción, cambiar a sandbox pide confirmación explícita. Facturar contra el entorno equivocado tiene consecuencias fiscales reales (`04`).
- **Campos secretos enmascarados**, con opción de reemplazar (nunca de revelar). Copiar no está disponible.
- **Historial de cambios** por sección: quién cambió qué y cuándo.
- **Ayuda contextual** en cada campo: dónde se obtiene esa credencial en el proveedor.
- Los valores que provienen de variables de entorno se muestran como **solo lectura**, con la etiqueta de su origen.

---

## 6. Lectura de configuración en el código

Ningún módulo lee `os.environ` directamente para estos valores. Se usa un accesor único con cache:

```python
from apps.config import settings_service as cfg

token = cfg.get_secret('envia.token_prod')     # descifra al vuelo, nunca se loguea
delay = cfg.get_int('envia.request_delay_ms')  # con default del registro
```

- **Cache en memoria con TTL corto** (p. ej. 60 s) para no golpear la base en cada request.
- **Invalidación inmediata al guardar** vía Redis pub/sub, para que los workers de Celery tomen el valor nuevo sin reiniciar. Este punto es fácil de olvidar: sin él, un cambio en el panel no llega a las tareas en segundo plano.
- Si falta una credencial requerida, la operación falla con un mensaje accionable (*"Falta el token de Envia. Configúralo en Configuración → Integraciones"*), nunca con un error genérico del proveedor.

---

## 7. API

```
GET   /api/v1/config/                      # registro + valores (secretos enmascarados)
GET   /api/v1/config/{group}/              # por integración
PATCH /api/v1/config/                      # actualizar (requiere step-up auth)
POST  /api/v1/config/{group}/test/         # probar conexión
GET   /api/v1/config/audit/?key=           # historial de cambios
POST  /api/v1/config/{key}/rotate/         # rotación de credencial
```

Todos los endpoints exigen `ADMIN` + `can_manage_config`. El `PATCH` exige token de re-autenticación reciente.

---

## 8. Casos límite

| Caso | Manejo |
|---|---|
| Se guarda una credencial inválida | "Probar conexión" es obligatorio antes de activar; si falla, se guarda como inactiva y las tareas siguen con la anterior. |
| Cambio de credencial con tareas en vuelo | Versión anterior retenida unos minutos; las tareas en curso terminan con la que tomaron. |
| Se pierde `SEEDS_SECRETS_KEY` | Los secretos son irrecuperables por diseño. Debe estar respaldada en el gestor de secretos de la organización. Documentar el procedimiento de recuperación: recargar cada credencial desde su proveedor. |
| Cambio accidental sandbox → producción en Alegra | Confirmación explícita + distintivo visible + registro en auditoría. |
| Un worker no ve el cambio | Invalidación por pub/sub + TTL corto como red de seguridad. |
| Alguien intenta leer un secreto por la API | Imposible: el serializer nunca expone el valor, solo la máscara. |
| Fuga por logs | Scrubbing de claves sensibles en logging, `IntegrationLog` y reportes de error. |
