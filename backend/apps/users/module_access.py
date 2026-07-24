from __future__ import annotations

import json
import logging
from copy import deepcopy

from apps.users.models import Role

logger = logging.getLogger(__name__)

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
    {"key": "roles", "label": "Roles"},
    {"key": "geo", "label": "Geografía"},
    {"key": "settings", "label": "Configuración"},
]

ALL_MODULE_KEYS: list[str] = [m["key"] for m in MODULE_CATALOG]

# Built-in defaults (used until an admin saves auth.role_modules).
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

# ADMIN must keep these so they cannot lock themselves out of role admin.
ADMIN_LOCKED_MODULES = ("home", "users", "roles")


def _normalize_modules(modules: list | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in modules or []:
        key = str(m)
        if key in ALL_MODULE_KEYS and key not in seen:
            seen.add(key)
            out.append(key)
    if "home" not in seen:
        out = ["home", *out]
    return out


def _normalize_role_map(raw: dict | None) -> dict[str, list[str]]:
    base = deepcopy(ROLE_DEFAULT_MODULES)
    if not isinstance(raw, dict):
        return base
    for role, _label in Role.choices:
        if role in raw and isinstance(raw[role], list):
            base[role] = _normalize_modules(raw[role])
    # Keep admin able to manage users/roles
    admin_mods = list(base.get(Role.ADMIN, []))
    for locked in ADMIN_LOCKED_MODULES:
        if locked not in admin_mods:
            admin_mods.append(locked)
    base[Role.ADMIN] = _normalize_modules(admin_mods)
    return base


def load_role_modules() -> dict[str, list[str]]:
    """Effective role → modules map (DB override or built-in defaults)."""
    try:
        from apps.config import settings_service as cfg

        stored = cfg.get("auth.role_modules")
        if isinstance(stored, dict) and stored:
            return _normalize_role_map(stored)
    except Exception:
        logger.exception("No se pudo leer auth.role_modules; usando defaults")
    return deepcopy(ROLE_DEFAULT_MODULES)


def save_role_modules(role_map: dict, *, actor=None, ip: str | None = None) -> dict[str, list[str]]:
    from apps.config import settings_service as cfg

    normalized = _normalize_role_map(role_map)
    cfg.set_value(
        "auth.role_modules",
        json.dumps(normalized, ensure_ascii=False),
        actor=actor,
        ip=ip,
    )
    return normalized


def default_modules_for_role(role: str) -> list[str]:
    mapping = load_role_modules()
    return list(mapping.get(role, mapping.get(Role.VIEWER, ["home"])))


def effective_modules(*, role: str, modules_override: list | None) -> list[str]:
    """Non-empty user.modules override wins; otherwise role map (propagates to all users)."""
    override = _normalize_modules(modules_override) if modules_override else []
    # Empty list means "use role" — distinguish from accidental empty after normalize of []
    if modules_override:
        raw = [str(m) for m in modules_override if str(m) in ALL_MODULE_KEYS]
        if raw:
            return _normalize_modules(raw)
    return default_modules_for_role(role)


def user_effective_modules(user) -> list[str]:
    return effective_modules(role=user.role, modules_override=getattr(user, "modules", None))
