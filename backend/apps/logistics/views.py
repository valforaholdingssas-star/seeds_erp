from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.logistics.models import (
    BatchItemStatus,
    BatchJob,
    BatchJobStatus,
    BatchJobType,
    BatchJobItem,
    Shipment,
    ShipmentStatus,
)
from apps.logistics.serializers import (
    BatchJobSerializer,
    IdsSerializer,
    ShipmentMirrorUpdateSerializer,
    ShipmentSerializer,
)
from apps.logistics.services.formatting import format_shipment
from apps.logistics.services.packing import packing_summary
from apps.logistics.services.labels_pdf import merge_shipment_label_pdfs
from apps.logistics.services.shipments import (
    generate_shipment_guide,
    mark_shipment_cancelled_local,
    mark_shipments_sent,
    reopen_shipment_for_regenerate,
)
from apps.logistics.tasks import enqueue_generate_shipments, run_format_batch
from apps.sales.models import SaleState
from apps.users.permissions import IsModuleRole


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class ShipmentViewSet(viewsets.ModelViewSet):
    permission_module = "logistics"
    queryset = (
        Shipment.objects.select_related("sale", "geo_city")
        .prefetch_related("sale__items")
        .filter(sale__state=SaleState.ACTIVE)
        .exclude(status=ShipmentStatus.ENVIADO)
    )
    serializer_class = ShipmentSerializer
    filterset_fields = [
        "status",
        "warning",
        "do_not_ship",
        "carrier",
        "tracking_number",
        "city_mirror",
    ]
    search_fields = [
        "sale__external_id",
        "sale__customer_name",
        "address_mirror",
        "city_mirror",
        "tracking_number",
        "last_error",
    ]
    ordering_fields = ["created_at", "status", "shipping_cost", "city_mirror"]

    def get_permissions(self):
        self.module_roles = ["LOGISTICA", "VENTAS", "SUPERVISOR", "VIEWER"]
        if self.action in {"list", "retrieve"}:
            return [IsModuleRole()]
        self.module_roles = ["LOGISTICA", "VENTAS"]
        return [IsModuleRole()]

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return ShipmentMirrorUpdateSerializer
        return ShipmentSerializer

    def get_queryset(self):
        qs = (
            Shipment.objects.select_related("sale", "geo_city")
            .prefetch_related("sale__items")
            .filter(sale__state=SaleState.ACTIVE)
        )
        include_sent = self.request.query_params.get("include_sent")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            return qs.filter(status=status_filter)
        if include_sent == "1":
            return qs
        return qs.exclude(status=ShipmentStatus.ENVIADO)

    def perform_update(self, serializer):
        shipment = serializer.save()
        log_audit_event(
            actor=self.request.user,
            action="SHIPMENT_MIRROR_UPDATED",
            entity="Shipment",
            entity_id=str(shipment.id),
            ip=_client_ip(self.request),
        )

    @action(detail=True, methods=["post"], url_path="format-ai")
    def format_ai(self, request, pk=None):
        shipment = self.get_object()
        format_shipment(shipment)
        return Response(ShipmentSerializer(shipment).data)

    @action(detail=False, methods=["post"], url_path="format-ai")
    def format_ai_batch(self, request):
        ser = IdsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ids = ser.validated_data["ids"]
        batch = BatchJob.objects.create(
            job_type=BatchJobType.FORMAT_ADDRESSES,
            status=BatchJobStatus.PENDING,
            total=len(ids),
            created_by=request.user,
        )
        for sid in ids:
            BatchJobItem.objects.create(
                batch=batch,
                ref_type="Shipment",
                ref_id=str(sid),
                status=BatchItemStatus.PENDING,
            )
        run_format_batch.delay(str(batch.id))
        return Response(BatchJobSerializer(batch).data, status=202)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        ser = IdsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ids = ser.validated_data["ids"]
        # Skip already tracked
        eligible = list(
            Shipment.objects.filter(id__in=ids)
            .exclude(tracking_number__gt="")
            .values_list("id", flat=True)
        )
        batch = BatchJob.objects.create(
            job_type=BatchJobType.GENERATE_SHIPMENTS,
            status=BatchJobStatus.PENDING,
            total=len(eligible),
            created_by=request.user,
        )
        for sid in eligible:
            BatchJobItem.objects.create(
                batch=batch,
                ref_type="Shipment",
                ref_id=str(sid),
                status=BatchItemStatus.PENDING,
            )
        enqueue_generate_shipments.delay(str(batch.id), str(request.user.id))
        return Response(BatchJobSerializer(batch).data, status=202)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        shipment = self.get_object()
        if shipment.tracking_number:
            return Response({"detail": "Ya tiene guía."}, status=400)
        if shipment.status not in {ShipmentStatus.GUIA_FALLIDA, ShipmentStatus.POR_GENERAR}:
            return Response({"detail": "Solo se reintenta desde fallida/por generar."}, status=400)
        shipment = generate_shipment_guide(shipment.id, actor=request.user)
        return Response(ShipmentSerializer(shipment).data)

    @action(detail=True, methods=["post"], url_path="cancel-local")
    def cancel_local(self, request, pk=None):
        """Mark cancelled in Seeds after the user cancels the guide manually in Envia."""
        try:
            shipment = mark_shipment_cancelled_local(self.get_object().id, actor=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(ShipmentSerializer(shipment).data)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        """Clear cancelled guide fields so a new Envia label can be generated."""
        try:
            shipment = reopen_shipment_for_regenerate(self.get_object().id, actor=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(ShipmentSerializer(shipment).data)

    @action(detail=False, methods=["post"], url_path="bulk-update")
    def bulk_update(self, request):
        ids = request.data.get("ids") or []
        fields = request.data.get("fields") or {}
        allowed = {"address_mirror", "city_mirror", "state_mirror"}
        patch = {k: v for k, v in fields.items() if k in allowed}
        if not ids or not patch:
            return Response({"detail": "ids y fields requeridos"}, status=400)
        updated = Shipment.objects.filter(id__in=ids).update(**patch)
        return Response({"updated": updated})


class BatchJobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_module = "logistics"
    queryset = BatchJob.objects.prefetch_related("items").all()
    serializer_class = BatchJobSerializer

    def get_permissions(self):
        self.module_roles = ["LOGISTICA", "VENTAS", "SUPERVISOR", "ADMIN"]
        return [IsModuleRole()]


class DispatchListView(APIView):
    permission_module = "dispatch"
    module_roles = ["LOGISTICA", "SUPERVISOR", "VIEWER"]
    permission_classes = [IsModuleRole]

    def get(self, request):
        sent = request.query_params.get("sent") == "1"
        qs = (
            Shipment.objects.select_related("sale")
            .prefetch_related("sale__items")
            .filter(status=ShipmentStatus.ENVIADO if sent else ShipmentStatus.LISTO_PARA_ENVIAR)
            .order_by("-sent_at" if sent else "-updated_at")
        )
        return Response(ShipmentSerializer(qs, many=True).data)


class DispatchPackSummaryView(APIView):
    """Vista de empaque: cuántos pedidos y unidades por producto (cajas)."""

    permission_module = "dispatch"
    module_roles = ["LOGISTICA", "SUPERVISOR", "VIEWER"]
    permission_classes = [IsModuleRole]

    def get(self, request):
        sent = request.query_params.get("sent") == "1"
        return Response(packing_summary(sent=sent))


class DispatchMarkSentView(APIView):
    permission_module = "dispatch"
    permission_crud = "u"
    module_roles = ["LOGISTICA"]
    permission_classes = [IsModuleRole]

    def post(self, request):
        ser = IdsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        updated = mark_shipments_sent(ser.validated_data["ids"], actor=request.user)
        return Response(
            {
                "updated": len(updated),
                "shipments": ShipmentSerializer(updated, many=True).data,
            }
        )


class DispatchLabelsPdfView(APIView):
    """Merge selected shipment label PDFs into one file for printing."""

    permission_module = "dispatch"
    permission_crud = "r"
    module_roles = ["LOGISTICA", "SUPERVISOR"]
    permission_classes = [IsModuleRole]

    def post(self, request):
        from django.http import HttpResponse

        ser = IdsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            pdf_bytes = merge_shipment_label_pdfs(ser.validated_data["ids"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {"detail": f"Error al unir PDFs: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="guias-despacho.pdf"'
        return response
