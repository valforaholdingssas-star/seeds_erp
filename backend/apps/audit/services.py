from __future__ import annotations

from typing import Any

from apps.audit.models import AuditLog


def log_audit_event(
    *,
    actor=None,
    action: str,
    entity: str,
    entity_id: str = "",
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity=entity,
        entity_id=str(entity_id or ""),
        metadata=metadata or {},
        ip_address=ip,
    )
