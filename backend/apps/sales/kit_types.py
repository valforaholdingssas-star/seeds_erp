"""Tipos de kit Seeds: tamaño del kit + color + cantidad de kits."""

from __future__ import annotations

import re

from django.db import models


class KitType(models.TextChoices):
    KIT_10 = "KIT_10", "Kit de 10 semillas"
    KIT_20 = "KIT_20", "Kit de 20 semillas"
    KIT_30 = "KIT_30", "Kit de 30 semillas"


KIT_TYPE_ALIASES: dict[str, str] = {
    "kit_10": KitType.KIT_10,
    "kit10": KitType.KIT_10,
    "10": KitType.KIT_10,
    "kit de 10": KitType.KIT_10,
    "kit de 10 semillas": KitType.KIT_10,
    "10 semillas": KitType.KIT_10,
    "kit 10": KitType.KIT_10,
    "kit_20": KitType.KIT_20,
    "kit20": KitType.KIT_20,
    "20": KitType.KIT_20,
    "kit de 20": KitType.KIT_20,
    "kit de 20 semillas": KitType.KIT_20,
    "20 semillas": KitType.KIT_20,
    "kit 20": KitType.KIT_20,
    "kit_30": KitType.KIT_30,
    "kit30": KitType.KIT_30,
    "30": KitType.KIT_30,
    "kit de 30": KitType.KIT_30,
    "kit de 30 semillas": KitType.KIT_30,
    "30 semillas": KitType.KIT_30,
    "kit 30": KitType.KIT_30,
}


def normalize_kit_type(raw: str | None) -> str:
    """Map free text / historical values to KIT_10 | KIT_20 | KIT_30 (or '')."""
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    if text in KitType.values:
        return text
    key = re.sub(r"\s+", " ", text.lower().replace("-", " ").replace("_", " ")).strip()
    key_compact = key.replace(" ", "")
    if key in KIT_TYPE_ALIASES:
        return KIT_TYPE_ALIASES[key]
    if key_compact in KIT_TYPE_ALIASES:
        return KIT_TYPE_ALIASES[key_compact]
    # "kit de 30 semillas", "seeds 20", etc.
    m = re.search(r"\b(10|20|30)\b", key)
    if m:
        return KIT_TYPE_ALIASES[m.group(1)]
    return text  # preserve unknown historical values


def kit_type_label(code: str | None) -> str:
    if not code:
        return ""
    normalized = normalize_kit_type(code)
    try:
        return KitType(normalized).label
    except ValueError:
        return str(code)


def infer_kit_type_from_name(product_name: str | None) -> str:
    return normalize_kit_type(product_name or "")
