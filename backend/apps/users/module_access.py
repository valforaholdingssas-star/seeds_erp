from __future__ import annotations

from apps.users.models import Role

# Keys used by nav + user.modules overrides.
MODULE_CATALOG: list[dict[str, str]] = [
    {"key": "home", "label": "Inicio"},
    {"key": "sales", "label": "Ventas"},
    {"key": "leads", "label": "Leads"},
    {"key": "analytics", "label": "Métricas"},
    {"key": "ai", "label": "Asistente"},
    {"key": "logistics", "label": "Envíos"},
    {"key": "dispatch", "label": "Despachos"},
    {"key": "inventory", "label": "Inventario"},
    {"key": "accounting", "label": "Contabilidad"},
    {"key": "integrations", "label": "Eventos / integraciones"},
    {"key": "sellers", "label": "Vendedores"},
    {"key": "payment_methods", "label": "Medios de pago"},
    {"key": "pack_rules", "label": "Pack rules"},
    {"key": "users", "label": "Usuarios"},
    {"key": "geo", "label": "Geografía"},
    {"key": "settings", "label": "Configuración"},
]

ALL_MODULE_KEYS: list[str] = [m["key"] for m in MODULE_CATALOG]

ROLE_DEFAULT_MODULES: dict[str, list[str]] = {
    Role.ADMIN: list(ALL_MODULE_KEYS),
    Role.VENTAS: [
        "home",
        "sales",
        "leads",
        "analytics",
        "ai",
        "logistics",
        "integrations",
        "accounting",
    ],
    Role.LOGISTICA: [
        "home",
        "sales",
        "analytics",
        "logistics",
        "dispatch",
        "inventory",
        "geo",
    ],
    Role.CONTABILIDAD: [
        "home",
        "sales",
        "analytics",
        "accounting",
        "inventory",
    ],
    Role.SUPERVISOR: [
        "home",
        "sales",
        "leads",
        "analytics",
        "ai",
        "logistics",
        "dispatch",
        "inventory",
        "accounting",
        "integrations",
        "geo",
    ],
    Role.VIEWER: [
        "home",
        "sales",
        "leads",
        "analytics",
        "logistics",
        "dispatch",
        "inventory",
        "accounting",
    ],
}


def default_modules_for_role(role: str) -> list[str]:
    return list(ROLE_DEFAULT_MODULES.get(role, ROLE_DEFAULT_MODULES[Role.VIEWER]))


def effective_modules(*, role: str, modules_override: list | None) -> list[str]:
    """Empty override → role defaults. ADMIN always keeps full catalog unless override set."""
    override = [str(m) for m in (modules_override or []) if str(m) in ALL_MODULE_KEYS]
    if override:
        # Always keep home reachable
        if "home" not in override:
            override = ["home", *override]
        return override
    return default_modules_for_role(role)


def user_effective_modules(user) -> list[str]:
    return effective_modules(role=user.role, modules_override=getattr(user, "modules", None))
