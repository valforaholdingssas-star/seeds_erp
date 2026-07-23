from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.geo.models import GeoCatalog
from apps.geo.serializers import GeoCatalogSerializer
from apps.geo.services import resolve_city
from apps.users.permissions import IsAdminOrSupervisor


class GeoCatalogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GeoCatalog.objects.all()
    serializer_class = GeoCatalogSerializer
    permission_classes = [IsAdminOrSupervisor]
    filterset_fields = ["department_iso", "municipality_code", "department"]
    search_fields = ["municipality", "department", "municipality_code", "search"]
    ordering_fields = ["municipality", "department", "municipality_code"]

    @action(detail=False, methods=["get"])
    def resolve(self, request):
        q = request.query_params.get("q", "")
        matches = resolve_city(q)
        return Response(
            {
                "query": q,
                "matches": GeoCatalogSerializer(matches, many=True).data,
            }
        )
