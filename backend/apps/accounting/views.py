from django.db.models import Sum
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import Customer, Invoice, InvoiceStatus, Refund
from apps.accounting.serializers import (
    CustomerSerializer,
    IdsSerializer,
    OptionalIdsSerializer,
    InvoiceSerializer,
    RefundCreateSerializer,
    RefundSerializer,
)
from apps.accounting.services.invoicing import (
    bulk_heal_customer_names,
    bulk_sync_customers_to_alegra,
    confirm_void,
    create_refund,
    issue_invoice,
    normalize_customer_documents,
    reconcile_invoice,
    sync_customer_to_alegra,
)
from apps.accounting.services.iva import build_iva_dashboard
from apps.accounting.tasks import enqueue_issue_invoices
from apps.logistics.models import BatchItemStatus, BatchJob, BatchJobStatus, BatchJobType, BatchJobItem
from apps.logistics.serializers import BatchJobSerializer
from apps.sales.models import ConsolidatedSale, SaleState
from apps.users.permissions import IsModuleRole


class CustomerViewSet(viewsets.ModelViewSet):
    permission_module = "accounting"
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filterset_fields = ["id_type", "id_number", "alegra_synced", "city"]
    search_fields = ["name", "id_number", "email", "phone"]
    ordering_fields = ["name", "created_at"]

    def get_permissions(self):
        self.module_roles = ["CONTABILIDAD", "SUPERVISOR", "VIEWER", "VENTAS", "ADMIN"]
        if self.action in {"list", "retrieve"}:
            return [IsModuleRole()]
        self.module_roles = ["CONTABILIDAD", "SUPERVISOR", "ADMIN"]
        return [IsModuleRole()]

    @action(detail=True, methods=["post"], url_path="sync-alegra")
    def sync_alegra(self, request, pk=None):
        try:
            customer = sync_customer_to_alegra(self.get_object(), actor=request.user)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(CustomerSerializer(customer).data)

    @action(detail=False, methods=["post"], url_path="bulk-sync-alegra")
    def bulk_sync_alegra(self, request):
        ser = IdsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = bulk_sync_customers_to_alegra(
            ser.validated_data["ids"], actor=request.user
        )
        status_code = 200 if result["failed"] == 0 else 207
        return Response(result, status=status_code)

    @action(detail=False, methods=["post"], url_path="bulk-normalize-documents")
    def bulk_normalize_documents(self, request):
        ser = OptionalIdsSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        ids = ser.validated_data.get("ids") or []
        result = normalize_customer_documents(ids or None, actor=request.user)
        status_code = 200 if result["failed"] == 0 else 207
        return Response(result, status=status_code)

    @action(detail=False, methods=["post"], url_path="bulk-heal-names")
    def bulk_heal_names(self, request):
        ser = OptionalIdsSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        ids = ser.validated_data.get("ids") or []
        limit = int(request.data.get("limit") or 120)
        unsynced_only = bool(request.data.get("unsynced_only"))
        result = bulk_heal_customer_names(
            ids or None,
            actor=request.user,
            limit=max(1, min(limit, 250)),
            unsynced_only=unsynced_only,
        )
        status_code = 200 if result["failed"] == 0 else 207
        return Response(result, status=status_code)

class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_module = "accounting"
    queryset = Invoice.objects.select_related("sale", "customer").all()
    serializer_class = InvoiceSerializer
    filterset_fields = ["status", "customer", "number", "idempotency_key"]
    search_fields = ["number", "alegra_id", "sale__external_id", "customer__name", "customer__id_number"]
    ordering_fields = ["created_at", "total", "status", "confirmed_at"]

    def get_permissions(self):
        self.module_roles = ["CONTABILIDAD", "SUPERVISOR", "VIEWER", "VENTAS"]
        if self.action in {"list", "retrieve"}:
            return [IsModuleRole()]
        self.module_roles = ["CONTABILIDAD"]
        return [IsModuleRole()]

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        try:
            invoice = issue_invoice(self.get_object().id, actor=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"])
    def reconcile(self, request, pk=None):
        invoice = reconcile_invoice(self.get_object().id, actor=request.user)
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=False, methods=["post"], url_path="bulk-issue")
    def bulk_issue(self, request):
        ser = IdsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ids = list(
            Invoice.objects.filter(
                id__in=ser.validated_data["ids"],
                status__in=[InvoiceStatus.POR_GENERAR, InvoiceStatus.FALLIDA],
                customer__alegra_synced=True,
            )
            .exclude(customer__alegra_id="")
            .values_list("id", flat=True)
        )
        if not ids:
            return Response(
                {
                    "detail": (
                        "Ninguna factura seleccionada tiene el contacto ya "
                        "sincronizado con Alegra."
                    )
                },
                status=400,
            )
        batch = BatchJob.objects.create(
            job_type=BatchJobType.ISSUE_INVOICES,
            status=BatchJobStatus.PENDING,
            total=len(ids),
            created_by=request.user,
        )
        for iid in ids:
            BatchJobItem.objects.create(
                batch=batch,
                ref_type="Invoice",
                ref_id=str(iid),
                status=BatchItemStatus.PENDING,
            )
        enqueue_issue_invoices.delay(str(batch.id), str(request.user.id))
        return Response(BatchJobSerializer(batch).data, status=202)


class RefundViewSet(viewsets.ModelViewSet):
    permission_module = "accounting"
    queryset = Refund.objects.select_related("invoice", "sale", "created_by").all()
    serializer_class = RefundSerializer
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["status", "manual_void_pending"]
    search_fields = ["reason", "alegra_credit_note_id", "sale__external_id"]

    def get_permissions(self):
        self.module_roles = ["CONTABILIDAD", "SUPERVISOR", "VIEWER"]
        if self.action in {"list", "retrieve"}:
            return [IsModuleRole()]
        self.module_roles = ["CONTABILIDAD"]
        return [IsModuleRole()]

    def create(self, request, *args, **kwargs):
        ser = RefundCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            refund = create_refund(
                ser.validated_data["invoice_id"],
                reason=ser.validated_data["reason"],
                actor=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(RefundSerializer(refund).data, status=201)

    @action(detail=True, methods=["post"], url_path="confirm-void")
    def confirm_void_action(self, request, pk=None):
        refund = confirm_void(self.get_object().id, actor=request.user)
        return Response(RefundSerializer(refund).data)


class IvaSummaryView(APIView):
    permission_module = "accounting"
    module_roles = ["CONTABILIDAD", "SUPERVISOR", "VIEWER", "ADMIN"]
    permission_classes = [IsModuleRole]

    def get(self, request):
        date_from = parse_date(request.query_params.get("from") or "")
        date_to = parse_date(request.query_params.get("to") or "")
        year_raw = (request.query_params.get("year") or "").strip()
        year = int(year_raw) if year_raw.isdigit() else None
        data = build_iva_dashboard(year=year, date_from=date_from, date_to=date_to)
        if request.query_params.get("channel"):
            # Channel filter kept for compatibility on the simple range cards.
            channel = request.query_params.get("channel")
            sales = ConsolidatedSale.objects.filter(state=SaleState.ACTIVE, source=channel)
            invoices = Invoice.objects.filter(status=InvoiceStatus.GENERADA, sale__source=channel)
            if date_from:
                sales = sales.filter(closed_at__date__gte=date_from)
                invoices = invoices.filter(confirmed_at__date__gte=date_from)
            if date_to:
                sales = sales.filter(closed_at__date__lte=date_to)
                invoices = invoices.filter(confirmed_at__date__lte=date_to)
            sales_agg = sales.aggregate(
                iva=Sum("iva_generated"),
                net=Sum("net_value"),
                total=Sum("total_value"),
            )
            inv_agg = invoices.aggregate(iva=Sum("iva"), total=Sum("total"))
            data["channel"] = channel
            data["iva_recaudado"]["amount"] = str(sales_agg["iva"] or 0)
            data["iva_recaudado"]["net_value"] = str(sales_agg["net"] or 0)
            data["iva_recaudado"]["total_value"] = str(sales_agg["total"] or 0)
            data["iva_recaudado"]["count"] = sales.count()
            data["iva_facturado"]["amount"] = str(inv_agg["iva"] or 0)
            data["iva_facturado"]["total"] = str(inv_agg["total"] or 0)
            data["iva_facturado"]["count"] = invoices.count()
            data["sales"] = {
                "iva_generated": data["iva_recaudado"]["amount"],
                "net_value": data["iva_recaudado"]["net_value"],
                "total_value": data["iva_recaudado"]["total_value"],
                "count": data["iva_recaudado"]["count"],
            }
            data["invoices"] = {
                "iva": data["iva_facturado"]["amount"],
                "total": data["iva_facturado"]["total"],
                "count": data["iva_facturado"]["count"],
            }
        return Response(data)
