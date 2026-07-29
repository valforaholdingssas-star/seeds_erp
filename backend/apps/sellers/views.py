from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import log_audit_event
from apps.sellers.models import Vendedor
from apps.sellers.serializers import VendedorSerializer
from apps.sellers.services import ensure_system_vendors, resolve_vendedor
from apps.sellers.goals import goals_matrix, upsert_goals
from apps.users.permissions import IsAdmin, IsModuleRole


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class VendedorViewSet(viewsets.ModelViewSet):
    permission_module = "sellers"
    queryset = Vendedor.objects.select_related("user").all()
    serializer_class = VendedorSerializer
    filterset_fields = ["active", "is_system", "needs_review", "name"]
    search_fields = ["name", "aliases"]
    ordering_fields = ["name", "created_at", "active", "needs_review"]

    def get_permissions(self):
        return [IsModuleRole()]

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

    @action(detail=False, methods=["get", "put"], url_path="monthly-goals")
    def monthly_goals(self, request):
        """
        GET  ?year=2026 → matriz comercial × meses
        PUT  {year, items:[{seller_id, month, amount}]} → upsert celdas
        """
        try:
            year = int(request.query_params.get("year") or request.data.get("year") or 0)
        except (TypeError, ValueError):
            year = 0
        if year < 2000 or year > 2100:
            from django.utils import timezone

            year = timezone.localdate().year

        if request.method == "GET":
            return Response(goals_matrix(year=year))

        items = request.data.get("items") or []
        if not isinstance(items, list):
            return Response(
                {"detail": "items debe ser una lista."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = upsert_goals(year=year, items=items)
        log_audit_event(
            actor=request.user,
            action="SELLER_MONTHLY_GOALS_UPSERT",
            entity="SellerMonthlyGoal",
            entity_id=str(year),
            metadata={"saved": result.get("saved"), "deleted": result.get("deleted")},
            ip=_client_ip(request),
        )
        return Response(result)

    @action(detail=False, methods=["get"])
    def resolve(self, request):
        raw = request.query_params.get("q", "")
        vendor = resolve_vendedor(raw, create_if_missing=False)
        if not vendor:
            return Response({"query": raw, "match": None})
        return Response({"query": raw, "match": VendedorSerializer(vendor).data})
