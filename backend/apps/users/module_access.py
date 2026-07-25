from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any, Literal

from apps.users.models import Role

logger = logging.getLogger(__name__)

Crud = Literal["c", "r", "u", "d"]
CRUD_KEYS: tuple[Crud, ...] = ("c", "r", "u", "d")
CRUD_LABELS = {"c": "Crear", "r": "Ver", "u": "Editar", "d": "Eliminar"}

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
    {"key": "finance", "label": "Finanzas"},
    {"key": "expenses", "label": "Gastos"},
    {"key": "dashboard", "label": "Torre de control"},
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

# Built-in module lists (legacy / seed for CRUD matrix).
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
        "dashboard",
    ],
    Role.LOGISTICA: [
        "home",
        "sales",
        "analytics",
        "logistics",
        "dispatch",
        "inventory",
        "geo",
        "dashboard",
    ],
    Role.CONTABILIDAD: [
        "home",
        "sales",
        "analytics",
        "accounting",
        "finance",
        "expenses",
        "dashboard",
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
        "finance",
        "expenses",
        "dashboard",
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
        "finance",
        "expenses",
        "dashboard",
    ],
}

ADMIN_LOCKED_MODULES = ("home", "users", "roles")


def empty_crud(*, c=False, r=False, u=False, d=False) -> dict[str, bool]:
    return {"c": bool(c), "r": bool(r), "u": bool(u), "d": bool(d)}


def full_crud() -> dict[str, bool]:
    return empty_crud(c=True, r=True, u=True, d=True)


def read_only_crud() -> dict[str, bool]:
    return empty_crud(r=True)


def write_crud(*, delete: bool = True) -> dict[str, bool]:
    return empty_crud(c=True, r=True, u=True, d=delete)


def normalize_crud(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return empty_crud()
    return {
        "c": bool(raw.get("c") or raw.get("create")),
        "r": bool(raw.get("r") or raw.get("read")),
        "u": bool(raw.get("u") or raw.get("update")),
        "d": bool(raw.get("d") or raw.get("delete")),
    }


def crud_any(flags: dict[str, bool] | None) -> bool:
    if not flags:
        return False
    return any(flags.get(k) for k in CRUD_KEYS)


def modules_from_permissions(perms: dict[str, dict[str, bool]]) -> list[str]:
    return [m for m in ALL_MODULE_KEYS if crud_any(perms.get(m))]


def expand_module_list_to_crud(role: str, modules: list[str]) -> dict[str, dict[str, bool]]:
    """Legacy role→[modules] → role→{module→CRUD} using role heuristics."""
    out: dict[str, dict[str, bool]] = {}
    for key in modules:
        if key not in ALL_MODULE_KEYS:
            continue
        if role == Role.VIEWER:
            out[key] = read_only_crud()
        elif role == Role.SUPERVISOR:
            out[key] = write_crud(delete=False)
        elif role == Role.ADMIN:
            out[key] = full_crud()
        else:
            out[key] = write_crud(delete=True)
    if "home" not in out:
        out["home"] = read_only_crud() if role == Role.VIEWER else write_crud(delete=False)
    return out


def built_in_role_permissions() -> dict[str, dict[str, dict[str, bool]]]:
    return {
        role: expand_module_list_to_crud(role, mods)
        for role, mods in ROLE_DEFAULT_MODULES.items()
    }


def _normalize_role_permissions(
    raw: dict | None,
) -> dict[str, dict[str, dict[str, bool]]]:
    base = built_in_role_permissions()
    if not isinstance(raw, dict):
        return base

    for role, _label in Role.choices:
        value = raw.get(role)
        if value is None:
            continue
        # Legacy: role → ["sales", "leads"]
        if isinstance(value, list):
            base[role] = expand_module_list_to_crud(role, [str(x) for x in value])
            continue
        # New: role → { module: {c,r,u,d} }
        if isinstance(value, dict):
            role_map: dict[str, dict[str, bool]] = {}
            for mod, flags in value.items():
                if str(mod) not in ALL_MODULE_KEYS:
                    continue
                # Legacy nested: module: true
                if isinstance(flags, bool):
                    role_map[str(mod)] = full_crud() if flags else empty_crud()
                else:
                    crud = normalize_crud(flags)
                    if crud_any(crud):
                        role_map[str(mod)] = crud
            if "home" not in role_map:
                role_map["home"] = read_only_crud()
            # Newly catalogued modules inherit built-in defaults when absent from stored config
            for mod, crud in base.get(role, {}).items():
                if mod not in role_map:
                    role_map[mod] = crud
            base[role] = role_map

    # ADMIN locked modules always keep full access
    admin = dict(base.get(Role.ADMIN, {}))
    for locked in ADMIN_LOCKED_MODULES:
        admin[locked] = full_crud()
    # ADMIN always gets every catalog module
    for mod in ALL_MODULE_KEYS:
        if mod not in admin:
            admin[mod] = full_crud()
    base[Role.ADMIN] = admin
    return base


def load_role_permissions() -> dict[str, dict[str, dict[str, bool]]]:
    """Prefer auth.role_permissions; fall back to auth.role_modules list map."""
    try:
        from apps.config import settings_service as cfg

        stored = cfg.get("auth.role_permissions")
        if isinstance(stored, dict) and stored:
            return _normalize_role_permissions(stored)
        legacy = cfg.get("auth.role_modules")
        if isinstance(legacy, dict) and legacy:
            return _normalize_role_permissions(legacy)
    except Exception:
        logger.exception("No se pudo leer permisos de rol; usando defaults")
    return built_in_role_permissions()


def save_role_permissions(
    role_map: dict,
    *,
    actor=None,
    ip: str | None = None,
) -> dict[str, dict[str, dict[str, bool]]]:
    from apps.config import settings_service as cfg

    normalized = _normalize_role_permissions(role_map)
    cfg.set_value(
        "auth.role_permissions",
        json.dumps(normalized, ensure_ascii=False),
        actor=actor,
        ip=ip,
    )
    # Dual-write flattened module lists for older clients
    flat = {role: modules_from_permissions(perms) for role, perms in normalized.items()}
    try:
        cfg.set_value(
            "auth.role_modules",
            json.dumps(flat, ensure_ascii=False),
            actor=actor,
            ip=ip,
        )
    except Exception:
        logger.exception("Dual-write auth.role_modules failed")
    return normalized


# --- Compat aliases used by older callers ---


def load_role_modules() -> dict[str, list[str]]:
    return {
        role: modules_from_permissions(perms)
        for role, perms in load_role_permissions().items()
    }


def save_role_modules(role_map: dict, *, actor=None, ip: str | None = None) -> dict[str, list[str]]:
    saved = save_role_permissions(role_map, actor=actor, ip=ip)
    return {role: modules_from_permissions(perms) for role, perms in saved.items()}


def default_modules_for_role(role: str) -> list[str]:
    return modules_from_permissions(load_role_permissions().get(role, {}))


def default_permissions_for_role(role: str) -> dict[str, dict[str, bool]]:
    return deepcopy(load_role_permissions().get(role, {}))


def effective_permissions(
    *,
    role: str,
    modules_override: list | None = None,
    permissions_override: dict | None = None,
) -> dict[str, dict[str, bool]]:
    """
    permissions_override (dict module→CRUD) wins if non-empty.
    Else modules_override list expands with role heuristics.
    Else role matrix.
    """
    if isinstance(permissions_override, dict) and permissions_override:
        out: dict[str, dict[str, bool]] = {}
        for mod, flags in permissions_override.items():
            if str(mod) not in ALL_MODULE_KEYS:
                continue
            crud = normalize_crud(flags)
            if crud_any(crud):
                out[str(mod)] = crud
        if "home" not in out:
            out["home"] = read_only_crud()
        return out

    if modules_override:
        raw = [str(m) for m in modules_override if str(m) in ALL_MODULE_KEYS]
        if raw:
            return expand_module_list_to_crud(role, raw)

    return default_permissions_for_role(role)


def effective_modules(*, role: str, modules_override: list | None) -> list[str]:
    perms = effective_permissions(role=role, modules_override=modules_override)
    return modules_from_permissions(perms)


def user_effective_permissions(user) -> dict[str, dict[str, bool]]:
    return effective_permissions(
        role=user.role,
        modules_override=getattr(user, "modules", None),
        permissions_override=getattr(user, "module_permissions", None),
    )


def user_effective_modules(user) -> list[str]:
    return modules_from_permissions(user_effective_permissions(user))


def user_can(user, module: str, action: Crud) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    perms = user_effective_permissions(user)
    flags = perms.get(module) or empty_crud()
    return bool(flags.get(action))


# DRF action → CRUD letter
ACTION_TO_CRUD: dict[str, Crud] = {
    "list": "r",
    "retrieve": "r",
    "create": "c",
    "update": "u",
    "partial_update": "u",
    "destroy": "d",
    # Common custom actions
    "bulk_update": "u",
    "withdraw": "d",
    "import_csv": "c",
    "board": "r",
    "transition": "u",
    "bulk_status": "u",
    "alerts": "r",
    "issue": "u",
    "reconcile": "u",
    "bulk_issue": "u",
    "confirm_void": "d",
    "sync_alegra": "u",
    "bulk_sync_alegra": "u",
    "reprocess": "u",
    "format_ai": "u",
    "cancel_local": "d",
    "reopen": "u",
    "seed_system": "u",
    "resolve": "r",
    "bulk_classify": "u",
    "seed": "u",
}


def crud_for_view(view, request) -> Crud:
    explicit = getattr(view, "permission_crud", None)
    if explicit in CRUD_KEYS:
        return explicit  # type: ignore[return-value]
    action = getattr(view, "action", None)
    if action and action in ACTION_TO_CRUD:
        return ACTION_TO_CRUD[action]
    # Explicit override on view/action
    mapping = getattr(view, "action_crud", None) or {}
    if action and action in mapping:
        return mapping[action]
    method = (getattr(request, "method", "") or "GET").upper()
    if method in {"GET", "HEAD", "OPTIONS"}:
        return "r"
    if method == "POST":
        return "c"
    if method in {"PUT", "PATCH"}:
        return "u"
    if method == "DELETE":
        return "d"
    return "r"
