from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import log_audit_event
from apps.sellers.models import Vendedor
from apps.sellers.serializers import VendedorSerializer
from apps.sellers.services import ensure_system_vendors, resolve_vendedor
from apps.users.permissions import IsAdmin, IsModuleRole


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class VendedorViewSet(viewsets.ModelViewSet):
    queryset = Vendedor.objects.select_related("user").all()
    serializer_class = VendedorSerializer
    filterset_fields = ["active", "is_system", "needs_review", "name"]
    search_fields = ["name", "aliases"]
    ordering_fields = ["name", "created_at", "active", "needs_review"]

    def get_permissions(self):
        if self.action in {"list", "retrieve", "resolve"}:
            self.module_roles = ["VENTAS", "LOGISTICA", "CONTABILIDAD", "SUPERVISOR", "VIEWER"]
            return [IsModuleRole()]
        return [IsAdmin()]

    def perform_create(self, serializer):
        vendor = serializer.save()
        log_audit_event(
            actor=self.request.user,
            action="VENDEDOR_CREATED",
            entity="Vendedor",
            entity_id=str(vendor.id),
            metadata={"name": vendor.name},
            ip=_client_ip(self.request),
        )

    def perform_update(self, serializer):
        vendor = serializer.save()
        log_audit_event(
            actor=self.request.user,
            action="VENDEDOR_UPDATED",
            entity="Vendedor",
            entity_id=str(vendor.id),
            metadata={"name": vendor.name, "active": vendor.active},
            ip=_client_ip(self.request),
        )

    def destroy(self, request, *args, **kwargs):
        vendor = self.get_object()
        if vendor.is_system:
            return Response(
                {"detail": "No se puede eliminar un vendedor de sistema.", "code": "system_vendor"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entity_id = str(vendor.id)
        name = vendor.name
        vendor.delete()
        log_audit_event(
            actor=request.user,
            action="VENDEDOR_DELETED",
            entity="Vendedor",
            entity_id=entity_id,
            metadata={"name": name},
            ip=_client_ip(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], permission_classes=[IsAdmin])
    def seed_system(self, request):
        created = ensure_system_vendors(actor=request.user)
        return Response(
            {
                "created": VendedorSerializer(created, many=True).data,
                "detail": f"{len(created)} vendedores de sistema creados.",
            }
        )

    @action(detail=False, methods=["get"])
    def resolve(self, request):
        raw = request.query_params.get("q", "")
        vendor = resolve_vendedor(raw, create_if_missing=False)
        if not vendor:
            return Response({"query": raw, "match": None})
        return Response({"query": raw, "match": VendedorSerializer(vendor).data})
