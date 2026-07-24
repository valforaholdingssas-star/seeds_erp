from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import log_audit_event
from apps.leads.models import Lead
from apps.leads.serializers import LeadSerializer
from apps.leads.services import bulk_update_status, can_transition, transition_lead
from apps.users.permissions import IsModuleRole


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class LeadViewSet(viewsets.ModelViewSet):
    permission_module = "leads"
    queryset = Lead.objects.select_related("seller", "converted_sale").all()
    serializer_class = LeadSerializer
    filterset_fields = ["status", "source", "seller", "city"]
    search_fields = ["name", "email", "phone", "city", "notes"]
    ordering_fields = ["created_at", "updated_at", "name", "status"]

    def get_permissions(self):
        if self.action in {"list", "retrieve", "board"}:
            self.module_roles = ["VENTAS", "SUPERVISOR", "VIEWER", "LOGISTICA", "CONTABILIDAD"]
            return [IsModuleRole()]
        self.module_roles = ["VENTAS", "SUPERVISOR"]
        return [IsModuleRole()]

    def perform_create(self, serializer):
        lead = serializer.save()
        log_audit_event(
            actor=self.request.user,
            action="LEAD_CREATED",
            entity="Lead",
            entity_id=str(lead.id),
            metadata={"name": lead.name, "source": lead.source},
            ip=_client_ip(self.request),
        )

    def perform_update(self, serializer):
        lead = serializer.save()
        log_audit_event(
            actor=self.request.user,
            action="LEAD_UPDATED",
            entity="Lead",
            entity_id=str(lead.id),
            metadata={"status": lead.status},
            ip=_client_ip(self.request),
        )

    def destroy(self, request, *args, **kwargs):
        lead = self.get_object()
        entity_id = str(lead.id)
        lead.delete()
        log_audit_event(
            actor=request.user,
            action="LEAD_DELETED",
            entity="Lead",
            entity_id=entity_id,
            ip=_client_ip(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def board(self, request):
        """Kanban payload: leads grouped by status."""
        qs = self.filter_queryset(self.get_queryset())
        columns = {}
        for lead in qs[:500]:
            columns.setdefault(lead.status, []).append(LeadSerializer(lead).data)
        return Response({"columns": columns, "count": qs.count()})

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        lead = self.get_object()
        new_status = request.data.get("status")
        if not new_status:
            return Response(
                {"detail": "status es obligatorio.", "code": "missing_status"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not can_transition(lead.status, new_status):
            return Response(
                {
                    "detail": f"Transición inválida: {lead.status} → {new_status}",
                    "code": "invalid_transition",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            lead = transition_lead(lead, status=new_status, actor=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(LeadSerializer(lead).data)

    @action(detail=False, methods=["post"])
    def bulk_status(self, request):
        ids = request.data.get("ids") or []
        new_status = request.data.get("status")
        if not ids or not new_status:
            return Response(
                {"detail": "ids y status son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = bulk_update_status(ids, status=new_status, actor=request.user)
        return Response(result)
