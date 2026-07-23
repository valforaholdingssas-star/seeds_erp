from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from typing import Any

from django.core.cache import cache
from django.db import transaction

from apps.audit.services import log_audit_event
from apps.common.exceptions import ConfigurationError
from apps.config.crypto import decrypt_secret, encrypt_secret, mask_secret
from apps.config.models import SettingAudit, SettingAuditAction, SettingValue
from apps.config.registry import SETTINGS, SETTINGS_BY_KEY, Setting, SettingType

logger = logging.getLogger(__name__)

CACHE_TTL = 60
CACHE_PREFIX = "seeds:cfg:"


def _cache_key(key: str) -> str:
    return f"{CACHE_PREFIX}{key}"


def invalidate(key: str | None = None) -> None:
    if key:
        cache.delete(_cache_key(key))
        return
    for setting in SETTINGS:
        cache.delete(_cache_key(setting.key))


def _coerce(setting: Setting, raw: str | None) -> Any:
    if raw is None or raw == "":
        return setting.default
    if setting.type == SettingType.INT:
        return int(raw)
    if setting.type == SettingType.BOOL:
        return str(raw).lower() in {"1", "true", "yes", "on"}
    if setting.type == SettingType.DECIMAL:
        return Decimal(str(raw))
    if setting.type == SettingType.JSON:
        return json.loads(raw)
    if setting.type == SettingType.CHOICE:
        if setting.choices and raw not in setting.choices:
            raise ConfigurationError(f"Valor inválido para {setting.key}")
        return raw
    return raw


def _read_stored(key: str) -> tuple[str | None, str]:
    """Return (raw_value_or_none, source). source in {db, env, default}."""
    try:
        row = SettingValue.objects.filter(key=key).first()
    except Exception:
        row = None
    if row is not None:
        if row.is_secret:
            if not row.encrypted:
                return None, "db"
            try:
                return decrypt_secret(bytes(row.encrypted)), "db"
            except Exception:
                logger.exception("No se pudo descifrar setting %s", key)
                return None, "db"
        return row.value or None, "db"

    env_key = key.upper().replace(".", "_")
    env_val = os.environ.get(env_key)
    if env_val is not None:
        return env_val, "env"

    setting = SETTINGS_BY_KEY.get(key)
    if setting and setting.default is not None:
        return str(setting.default), "default"
    return None, "default"


def get_raw(key: str) -> str | None:
    cached = cache.get(_cache_key(key))
    if cached is not None:
        return cached if cached != "__NONE__" else None
    value, _source = _read_stored(key)
    cache.set(_cache_key(key), value if value is not None else "__NONE__", CACHE_TTL)
    return value


def get(key: str, default: Any = None) -> Any:
    setting = SETTINGS_BY_KEY.get(key)
    if not setting:
        raise ConfigurationError(f"Parámetro desconocido: {key}")
    raw = get_raw(key)
    if raw is None:
        return default if default is not None else setting.default
    return _coerce(setting, raw)


def get_secret(key: str) -> str | None:
    setting = SETTINGS_BY_KEY.get(key)
    if not setting or not setting.is_secret:
        raise ConfigurationError(f"{key} no es un secreto registrado")
    return get_raw(key)


def get_int(key: str, default: int | None = None) -> int:
    value = get(key, default)
    return int(value) if value is not None else 0


def get_bool(key: str, default: bool = False) -> bool:
    value = get(key, default)
    return bool(value)


def describe(key: str) -> dict[str, Any]:
    setting = SETTINGS_BY_KEY[key]
    raw, source = _read_stored(key)
    is_set = bool(raw)
    row = SettingValue.objects.filter(key=key).first()
    payload: dict[str, Any] = {
        "key": key,
        "label": setting.label,
        "group": setting.group,
        "type": setting.type.value,
        "help": setting.help,
        "required": setting.required,
        "choices": list(setting.choices),
        "is_secret": setting.is_secret,
        "is_set": is_set,
        "source": source,
        "version": row.version if row else 0,
        "updated_at": row.updated_at.isoformat() if row else None,
        "updated_by": (
            {"id": str(row.updated_by_id), "email": row.updated_by.email}
            if row and row.updated_by_id
            else None
        ),
    }
    if setting.is_secret:
        payload["masked"] = mask_secret(raw) if raw else ""
        payload["value"] = None
    else:
        payload["value"] = raw if raw is not None else (
            str(setting.default) if setting.default is not None else ""
        )
        payload["masked"] = None
    return payload


def list_group(group: str | None = None) -> list[dict[str, Any]]:
    keys = [
        s.key
        for s in SETTINGS
        if group is None or s.group == group.upper()
    ]
    return [describe(k) for k in keys]


@transaction.atomic
def set_value(
    key: str,
    value: str | None,
    *,
    actor=None,
    ip: str | None = None,
    rotate: bool = False,
) -> SettingValue:
    setting = SETTINGS_BY_KEY.get(key)
    if not setting:
        raise ConfigurationError(f"Parámetro desconocido: {key}")

    # Empty string on PATCH for secrets means "do not change"
    row = SettingValue.objects.filter(key=key).first()
    if setting.is_secret and (value is None or value == ""):
        if row:
            return row
        raise ConfigurationError(f"Debes enviar un valor para {key}")

    old_raw, _ = _read_stored(key)
    if row is None:
        row = SettingValue(key=key, is_secret=setting.is_secret)
        action = SettingAuditAction.CREATED
    else:
        action = SettingAuditAction.ROTATED if rotate else SettingAuditAction.UPDATED

    if setting.is_secret:
        row.encrypted = encrypt_secret(value or "")
        row.value = ""
        row.is_secret = True
    else:
        # Validate coerce
        _coerce(setting, value or "")
        row.value = value or ""
        row.encrypted = None
        row.is_secret = False

    row.version = (row.version or 0) + 1
    row.updated_by = actor if getattr(actor, "is_authenticated", False) else None
    row.save()

    SettingAudit.objects.create(
        key=key,
        actor=row.updated_by,
        action=action,
        old_value_masked=mask_secret(old_raw) if setting.is_secret else (old_raw or "")[:64],
        new_value_masked=mask_secret(value) if setting.is_secret else (value or "")[:64],
        ip_address=ip,
    )
    log_audit_event(
        actor=actor,
        action=f"SETTING_{action}",
        entity="SettingValue",
        entity_id=key,
        metadata={"key": key},
        ip=ip,
    )
    invalidate(key)
    return row
