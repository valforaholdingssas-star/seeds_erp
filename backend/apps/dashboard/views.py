from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.models import ControlIndicator
from apps.dashboard.serializers import ControlIndicatorSerializer, IndicatorSnapshotSerializer
from apps.dashboard.services.evaluate import dashboard_for_role, evaluate_indicator
from apps.dashboard.services.seed import seed_dashboard
from apps.users.permissions import IsModuleRole


class DashboardOverviewView(APIView):
    permission_classes = [IsModuleRole]
    permission_module = "dashboard"

    def get(self, request):
        role = getattr(request.user, "role", "VIEWER") or "VIEWER"
        module = request.query_params.get("module")
        return Response(dashboard_for_role(role, module=module))


class DashboardIndicatorDetailView(APIView):
    permission_classes = [IsModuleRole]
    permission_module = "dashboard"

    def get(self, request, key: str):
        ind = ControlIndicator.objects.filter(key=key).first()
        if not ind:
            return Response({"detail": "Indicador no encontrado"}, status=404)
        data = evaluate_indicator(ind)
        snaps = ind.snapshots.order_by("-captured_at")[:60]
        data["history"] = IndicatorSnapshotSerializer(snaps, many=True).data
        return Response(data)


class ControlIndicatorViewSet(viewsets.ModelViewSet):
    permission_module = "dashboard"
    queryset = ControlIndicator.objects.all()
    serializer_class = ControlIndicatorSerializer
    lookup_field = "key"
    filterset_fields = ["module", "visible", "severity"]
    search_fields = ["key", "label"]
    ordering_fields = ["order", "key"]

    def get_permissions(self):
        self.module_roles = ["ADMIN", "CONTABILIDAD", "SUPERVISOR", "VIEWER", "LOGISTICA", "VENTAS"]
        if self.action in {"list", "retrieve"}:
            return [IsModuleRole()]
        self.module_roles = ["ADMIN"]
        return [IsModuleRole()]


class SeedDashboardView(APIView):
    permission_classes = [IsModuleRole]
    permission_module = "dashboard"
    permission_crud = "u"

    def post(self, request):
        return Response(seed_dashboard(actor=request.user))
