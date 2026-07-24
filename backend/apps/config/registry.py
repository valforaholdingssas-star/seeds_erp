from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SettingType(str, Enum):
    STRING = "string"
    SECRET = "secret"
    INT = "int"
    BOOL = "bool"
    CHOICE = "choice"
    JSON = "json"
    DECIMAL = "decimal"


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    group: str
    type: SettingType
    required: bool = False
    default: Any = None
    help: str = ""
    choices: tuple[str, ...] = field(default_factory=tuple)
    is_secret: bool = False

    def __post_init__(self) -> None:
        if self.type == SettingType.SECRET:
            object.__setattr__(self, "is_secret", True)


SETTINGS: list[Setting] = [
    # Envia
    Setting(
        key="envia.environment",
        label="Entorno",
        group="ENVIA",
        type=SettingType.CHOICE,
        choices=("sandbox", "production"),
        default="sandbox",
        help="Sandbox para pruebas; producción genera guías reales.",
    ),
    Setting(
        key="envia.token_sandbox",
        label="Token sandbox",
        group="ENVIA",
        type=SettingType.SECRET,
        help="Se obtiene en Envia → Developers (sandbox).",
    ),
    Setting(
        key="envia.token_prod",
        label="Token de producción",
        group="ENVIA",
        type=SettingType.SECRET,
        help="Se obtiene en Envia → Developers (producción).",
    ),
    Setting(
        key="envia.request_delay_ms",
        label="Espera entre solicitudes",
        group="ENVIA",
        type=SettingType.INT,
        default=1200,
        help="Milisegundos entre guías. Súbelo si el proveedor bloquea.",
    ),
    Setting(
        key="envia.default_carrier",
        label="Carrier por defecto",
        group="ENVIA",
        type=SettingType.STRING,
        default="coordinadora",
    ),
    Setting(
        key="envia.default_service",
        label="Servicio por defecto",
        group="ENVIA",
        type=SettingType.STRING,
        default="ground",
    ),
    # Origen Seeds (punto de partida de guías) — editable si cambia la oficina
    Setting(
        key="envia.origin_company",
        label="Origen · empresa",
        group="ENVIA",
        type=SettingType.STRING,
        default="Seeds",
    ),
    Setting(
        key="envia.origin_email",
        label="Origen · email",
        group="ENVIA",
        type=SettingType.STRING,
        default="seeds.atencion@gmail.com",
    ),
    Setting(
        key="envia.origin_phone",
        label="Origen · teléfono",
        group="ENVIA",
        type=SettingType.STRING,
        default="3507047110",
    ),
    Setting(
        key="envia.origin_phone_code",
        label="Origen · phone_code",
        group="ENVIA",
        type=SettingType.STRING,
        default="CO",
    ),
    Setting(
        key="envia.origin_street",
        label="Origen · calle",
        group="ENVIA",
        type=SettingType.STRING,
        default="Ak 7 #155C-30",
    ),
    Setting(
        key="envia.origin_number",
        label="Origen · complemento",
        group="ENVIA",
        type=SettingType.STRING,
        default="North Point Torre E Oficina 1502",
    ),
    Setting(
        key="envia.origin_city",
        label="Origen · ciudad (DANE)",
        group="ENVIA",
        type=SettingType.STRING,
        default="11001000",
        help="Código DANE municipio origen (Bogotá = 11001000).",
    ),
    Setting(
        key="envia.origin_state",
        label="Origen · departamento",
        group="ENVIA",
        type=SettingType.STRING,
        default="DC",
        help="Código Envia de departamento (Bogotá = DC).",
    ),
    Setting(
        key="envia.origin_country",
        label="Origen · país",
        group="ENVIA",
        type=SettingType.STRING,
        default="CO",
    ),
    Setting(
        key="envia.origin_postal_code",
        label="Origen · postalCode",
        group="ENVIA",
        type=SettingType.STRING,
        default="",
        help="En CO suele ir vacío (como en n8n). Debe enviarse la clave aunque esté vacía.",
    ),
    Setting(
        key="envia.origin_identification",
        label="Origen · NIT / identificación",
        group="ENVIA",
        type=SettingType.STRING,
        default="901908375",
    ),
    # Alegra
    Setting(
        key="alegra.environment",
        label="Entorno",
        group="ALEGRA",
        type=SettingType.CHOICE,
        choices=("sandbox", "production"),
        default="sandbox",
    ),
    Setting(
        key="alegra.email",
        label="Email de la cuenta",
        group="ALEGRA",
        type=SettingType.STRING,
        help="Email con el que inicias sesión en Alegra.",
    ),
    Setting(
        key="alegra.token",
        label="Token API",
        group="ALEGRA",
        type=SettingType.SECRET,
        help="Token de API de Alegra (Basic Auth).",
    ),
    # WooCommerce
    Setting(
        key="woocommerce.store_url",
        label="URL de la tienda",
        group="WOOCOMMERCE",
        type=SettingType.STRING,
        help="Ej. https://tienda.seeds.co",
    ),
    Setting(
        key="woocommerce.consumer_key",
        label="Consumer key",
        group="WOOCOMMERCE",
        type=SettingType.SECRET,
    ),
    Setting(
        key="woocommerce.consumer_secret",
        label="Consumer secret",
        group="WOOCOMMERCE",
        type=SettingType.SECRET,
    ),
    Setting(
        key="woocommerce.webhook_secret",
        label="Secreto HMAC del webhook",
        group="WOOCOMMERCE",
        type=SettingType.SECRET,
    ),
    Setting(
        key="woocommerce.require_signature",
        label="Exigir firma HMAC",
        group="WOOCOMMERCE",
        type=SettingType.BOOL,
        default=True,
        help="Si es falso, permite webhooks sin secreto (solo local/dev).",
    ),
    Setting(
        key="woocommerce.id_meta_key",
        label="Clave meta de cédula",
        group="WOOCOMMERCE",
        type=SettingType.STRING,
        default="billing_cedula",
        help="Key en meta_data del pedido — nunca usar índice fijo.",
    ),
    # Kommo
    Setting(
        key="kommo.subdomain",
        label="Subdominio",
        group="KOMMO",
        type=SettingType.STRING,
        help="Ej. seeds → https://seeds.kommo.com",
    ),
    Setting(
        key="kommo.token",
        label="Token de larga duración",
        group="KOMMO",
        type=SettingType.SECRET,
    ),
    Setting(
        key="kommo.won_pipeline_id",
        label="Pipeline de venta ganada",
        group="KOMMO",
        type=SettingType.STRING,
        help="ID del pipeline; no hardcodear.",
    ),
    Setting(
        key="kommo.won_status_id",
        label="Columna de venta ganada",
        group="KOMMO",
        type=SettingType.STRING,
        help="status_id que dispara consolidación.",
    ),
    Setting(
        key="kommo.registered_pipeline_id",
        label="Pipeline «registrado en ERP»",
        group="KOMMO",
        type=SettingType.STRING,
        help="Opcional. Pipeline destino tras registrar la venta en el ERP.",
    ),
    Setting(
        key="kommo.registered_status_id",
        label="Columna «registrado en ERP»",
        group="KOMMO",
        type=SettingType.STRING,
        help="Tras consolidar, el lead se mueve aquí. Debe ser distinta a venta ganada.",
    ),
    # AI
    Setting(
        key="ai.provider",
        label="Proveedor",
        group="AI",
        type=SettingType.CHOICE,
        choices=("openai", "anthropic"),
        default="openai",
    ),
    Setting(
        key="ai.api_key",
        label="API key",
        group="AI",
        type=SettingType.SECRET,
    ),
    Setting(
        key="ai.model_format",
        label="Modelo formateo de direcciones",
        group="AI",
        type=SettingType.STRING,
        default="gpt-4o-mini",
    ),
    Setting(
        key="ai.enabled",
        label="IA activa",
        group="AI",
        type=SettingType.BOOL,
        default=True,
    ),
    # Business
    Setting(
        key="business.iva_rate",
        label="IVA (%)",
        group="BUSINESS",
        type=SettingType.DECIMAL,
        default="19",
        help="IVA Colombia. Por defecto 19.",
    ),
    Setting(
        key="business.timezone",
        label="Zona horaria",
        group="BUSINESS",
        type=SettingType.STRING,
        default="America/Bogota",
    ),
    Setting(
        key="business.currency",
        label="Moneda",
        group="BUSINESS",
        type=SettingType.STRING,
        default="COP",
    ),
    Setting(
        key="business.sales_goal_month",
        label="Meta de ventas mensual (COP)",
        group="BUSINESS",
        type=SettingType.DECIMAL,
        default="50000000",
        help="Alimenta KPIs de performance y proyección del panel.",
    ),
    Setting(
        key="inventory.allow_negative_stock",
        label="Permitir stock negativo",
        group="BUSINESS",
        type=SettingType.BOOL,
        default=True,
        help="Si es falso, el despacho falla cuando no hay existencia.",
    ),
]

SETTINGS_BY_KEY: dict[str, Setting] = {s.key: s for s in SETTINGS}
GROUPS = sorted({s.group for s in SETTINGS})
