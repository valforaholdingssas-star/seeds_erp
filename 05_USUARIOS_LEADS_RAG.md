# Seeds ERP — 05 · Usuarios/Roles, Leads y RAG de IA

> Requiere `00_ARQUITECTURA`. Apps: `apps/users`, `apps/leads`, e infraestructura RAG en `apps/integrations`/`apps/ai`.

---

## 1. Usuarios, roles y permisos

Base idéntica al backend de referencia adjunto (email + password + JWT, `AbstractBaseUser` + `PermissionsMixin`, `UserManager`, auditoría). Diferencias para Seeds:

```python
class Role(TextChoices):
    ADMIN='ADMIN'; VENTAS='VENTAS'; LOGISTICA='LOGISTICA'
    CONTABILIDAD='CONTABILIDAD'; SUPERVISOR='SUPERVISOR'; VIEWER='VIEWER'

class User(AbstractBaseUser, PermissionsMixin):
    id, full_name, id_type, id_number, email (USERNAME_FIELD, unique),
    phone, role (Role), status {ACTIVE|SUSPENDED}, timestamps, last_login_at
```

Permisos personalizados (DRF): `IsAdmin`, `IsAdminOrSupervisor`, `IsModuleRole('VENTAS'|'LOGISTICA'|'CONTABILIDAD')`, `IsOwnerOrAdmin`. Cerrado por defecto (`IsAuthenticated`).

Matriz por módulo (resumen):
| Módulo | ADMIN | VENTAS | LOGISTICA | CONTABILIDAD | SUPERVISOR | VIEWER |
|---|---|---|---|---|---|---|
| Ventas | RW | RW (propias/todas según config) | R | R | R | R |
| Logística/Despachos | RW | R | RW | R | R | R |
| Inventario | RW | R | RW | R | R | R |
| Contabilidad | RW | R | R | RW | R | R |
| Usuarios/Config | RW | — | — | — | R | — |

Auditoría (`audit.AuditLog`) obligatoria en: login, CRUD usuarios, cambios de rol, consolidación/edición de venta, generación/reintento de guía, emisión/anulación de factura, reembolso, ajustes de inventario. Servicio `log_audit_event(actor, action, entity, entity_id, metadata, ip)`.

---

## 2. Leads

Módulo simple de captura, base para automatización comercial futura.
```python
class Lead(BaseModel):
    name, email, phone, city, source (CharField),   # web, feria, referido, kommo...
    status (NUEVO|CONTACTADO|CALIFICADO|CONVERTIDO|DESCARTADO),
    seller = FK(sellers.Vendedor, null=True),
    notes, converted_sale = FK(sales.ConsolidatedSale, null=True),
    extra = JSONField()
```
- Kanban por `status` con drag&drop; filtro por todas las columnas; edición masiva.
- Al `CONVERTIDO`, se puede enlazar a la venta consolidada resultante.
- Ganchos futuros: automatizaciones comerciales (secuencias, recordatorios) — de ahí la "lógica comercial de automatización con clientes" mencionada en el objetivo.

---

## 3. RAG sobre la base de datos (capa de IA)

Objetivo: conectar IA al ERP para operaciones asistidas (formateo de direcciones ya visto en `02`; consultas en lenguaje natural sobre ventas/logística; automatizaciones). Diseño en dos capas:

### 3.1 Datos estructurados → "text-to-query" seguro
Para preguntas sobre datos vivos ("¿cuánto vendió VENDEDORA 1 esta semana?"), **no** se hace RAG vectorial: se usa un agente que llama **herramientas/endpoints definidos** (los de `analytics` y selectores existentes) con parámetros validados. Es más preciso y seguro que texto-a-SQL libre. El LLM elige la herramienta y los filtros; el ERP ejecuta la consulta con permisos del usuario. Nunca SQL arbitrario en producción.

### 3.2 RAG vectorial (pgvector) para conocimiento semi-estructurado
Para notas de pedido, síntomas, descripciones de producto, políticas, histórico de casos:
```python
class Document(BaseModel):
    kind (SALE_NOTE|PRODUCT|POLICY|SYMPTOM|CASE), ref_type, ref_id,
    content (Text), metadata (JSON)
class Embedding(BaseModel):
    document = FK(Document); chunk (Text);
    vector = VectorField(dimensions=1536)   # pgvector
```
- Ingesta: al crear/actualizar ventas/productos/notas, encolar task que trocea, embebe y guarda vectores.
- Recuperación: `similarity search` (coseno) filtrado por permisos + `metadata`.
- Orquestación: un servicio `ai/services/agent.py` que combina 3.1 (tools) + 3.2 (retrieval) y responde con citación de fuentes.

### 3.3 Guardrails
- El agente opera con la identidad/permisos del usuario (no ve lo que el usuario no puede ver).
- Acciones con efecto (crear guía, emitir factura) **nunca** se ejecutan autónomamente sin confirmación humana explícita — especialmente facturación (implicaciones fiscales, ver `04`).
- Todo prompt/response de IA con efecto queda en `IntegrationLog`/`AuditLog`.
- Secretos y PII: no enviar cédulas/datos sensibles al LLM salvo lo mínimo necesario para la tarea (p.ej. formateo de dirección).

### 3.4 Infra
- Extensiones Postgres: `vector`, `pg_trgm`, `postgis`.
- Proveedor LLM, API key, modelo y prompts **configurables desde el panel** (`07_CONFIGURACION §4.5`), no por variables de entorno; abstraer tras una interfaz para poder cambiar de modelo sin redeploy.
- Embeddings y chat vía la misma capa `integrations` con rate limiting y logging.
