from __future__ import annotations

import re
import unicodedata

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q

from apps.geo.models import GeoCatalog


def normalize_text(value: str) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


BLOCKED_CITY_TOKENS = {"", ".", "domicilio", "recoger", "n/a", "na", "none", "sin ciudad"}


def is_blocked_city(value: str) -> bool:
    return normalize_text(value) in BLOCKED_CITY_TOKENS


def resolve_city(raw: str, *, limit: int = 5) -> list[GeoCatalog]:
    """Exact → contains → trigram fuzzy. LLM fallback arrives in logistics module."""
    if is_blocked_city(raw):
        return []
    needle = normalize_text(raw)
    if not needle:
        return []

    exact = list(GeoCatalog.objects.filter(search=needle)[:limit])
    if exact:
        return exact

    contains = list(
        GeoCatalog.objects.filter(
            Q(search__icontains=needle) | Q(municipality__icontains=raw.strip())
        )[:limit]
    )
    if contains:
        return contains

    return list(
        GeoCatalog.objects.annotate(sim=TrigramSimilarity("search", needle))
        .filter(sim__gt=0.25)
        .order_by("-sim")[:limit]
    )
