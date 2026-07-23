from __future__ import annotations

from apps.audit.services import log_audit_event
from apps.leads.models import Lead, LeadStatus


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    LeadStatus.NUEVO: {
        LeadStatus.CONTACTADO,
        LeadStatus.CALIFICADO,
        LeadStatus.DESCARTADO,
        LeadStatus.CONVERTIDO,
    },
    LeadStatus.CONTACTADO: {
        LeadStatus.CALIFICADO,
        LeadStatus.DESCARTADO,
        LeadStatus.CONVERTIDO,
        LeadStatus.NUEVO,
    },
    LeadStatus.CALIFICADO: {
        LeadStatus.CONVERTIDO,
        LeadStatus.DESCARTADO,
        LeadStatus.CONTACTADO,
    },
    LeadStatus.CONVERTIDO: {LeadStatus.DESCARTADO},
    LeadStatus.DESCARTADO: {LeadStatus.NUEVO, LeadStatus.CONTACTADO},
}


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status == to_status:
        return True
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


def transition_lead(lead: Lead, *, status: str, actor=None, sale=None) -> Lead:
    if not can_transition(lead.status, status):
        raise ValueError(f"Transición inválida: {lead.status} → {status}")
    lead.status = status
    update_fields = ["status", "updated_at"]
    if sale is not None:
        lead.converted_sale = sale
        lead.status = LeadStatus.CONVERTIDO
        update_fields.extend(["converted_sale"])
    lead.save(update_fields=list(dict.fromkeys(update_fields)))
    log_audit_event(
        actor=actor,
        action="LEAD_STATUS_CHANGED",
        entity="Lead",
        entity_id=str(lead.id),
        metadata={"status": lead.status},
    )
    return lead


def bulk_update_status(lead_ids: list, *, status: str, actor=None) -> dict:
    updated = 0
    errors: list[dict] = []
    for lead in Lead.objects.filter(id__in=lead_ids):
        try:
            transition_lead(lead, status=status, actor=actor)
            updated += 1
        except ValueError as exc:
            errors.append({"id": str(lead.id), "detail": str(exc)})
    return {"updated": updated, "errors": errors}
