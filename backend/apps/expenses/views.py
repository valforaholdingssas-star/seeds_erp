from django.db.models import Prefetch, Q, Sum
from django.http import FileResponse, Http404
from django_filters import rest_framework as filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.expenses.models import (
    AttachmentKind,
    Expense,
    ExpenseAttachment,
    ExpenseStatus,
)
from apps.expenses.serializers import (
    BulkUpdateSerializer,
    CreatePayableSerializer,
    ExpenseAttachmentSerializer,
    ExpenseSerializer,
    ExpenseStatusSerializer,
    MarkPaidSerializer,
    ReconcileSerializer,
    TransitionSerializer,
)
from apps.expenses.services.amortization import regenerate_amortization
from apps.expenses.services.payables import create_payable, mark_payable_paid
from apps.expenses.services.reconcile import reconcile_expense, suggest_movements
from apps.expenses.services.seed import seed_expense_statuses
from apps.expenses.services.transitions import TransitionError, transition_expense
from apps.finance.models import BankMovement, FinancialAccount
from apps.users.permissions import IsModuleRole

ALLOWED_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}
MAX_UPLOAD_BYTES = 12 * 1024 * 1024


class ExpenseFilter(filters.FilterSet):
    status_key = filters.CharFilter(field_name="status__key")
    feeds_efe = filters.BooleanFilter(field_name="status__feeds_efe")
    date_from = filters.DateFilter(field_name="expense_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="expense_date", lookup_expr="lte")
    q = filters.CharFilter(method="filter_q")

    class Meta:
        model = Expense
        fields = [
            "status",
            "status_key",
            "bank_account",
            "efe_account",
            "responsible",
            "reconciled",
            "checked",
            "iva_already_discounted",
            "amortize",
            "feeds_efe",
        ]

    def filter_q(self, qs, name, value):
        if not value:
            return qs
        return qs.filter(
            Q(title__icontains=value)
            | Q(concept__icontains=value)
            | Q(efe_account__full_label__icontains=value)
        )


class ExpenseStatusViewSet(viewsets.ModelViewSet):
    permission_module = "expenses"
    queryset = ExpenseStatus.objects.all()
    serializer_class = ExpenseStatusSerializer
    filterset_fields = ["active", "feeds_efe"]
    search_fields = ["key", "label"]
    ordering_fields = ["order", "key"]

    def get_permissions(self):
        self.module_roles = ["CONTABILIDAD", "SUPERVISOR", "VIEWER", "ADMIN"]
        if self.action in {"list", "retrieve"}:
            return [IsModuleRole()]
        self.module_roles = ["CONTABILIDAD", "ADMIN"]
        return [IsModuleRole()]


class ExpenseViewSet(viewsets.ModelViewSet):
    permission_module = "expenses"
    serializer_class = ExpenseSerializer
    filterset_class = ExpenseFilter
    search_fields = ["title", "concept"]
    ordering_fields = ["expense_date", "amount", "created_at", "title"]

    def get_permissions(self):
        self.module_roles = ["CONTABILIDAD", "SUPERVISOR", "VIEWER", "ADMIN"]
        if self.action in {
            "list",
            "retrieve",
            "reimbursements",
            "iva",
            "suggest_movements",
            "payables",
        }:
            return [IsModuleRole()]
        self.module_roles = ["CONTABILIDAD", "SUPERVISOR", "ADMIN"]
        return [IsModuleRole()]

    def get_queryset(self):
        return (
            Expense.objects.select_related(
                "status",
                "bank_account",
                "efe_account",
                "accounting_account",
                "responsible",
                "created_by",
                "approved_by",
                "bank_movement",
            )
            .prefetch_related(
                Prefetch(
                    "attachments",
                    queryset=ExpenseAttachment.objects.order_by("-created_at"),
                ),
                "amortization_entries__efe_account",
            )
            .all()
        )

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        expense = self.get_object()
        ser = TransitionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            expense, warnings = transition_expense(
                expense,
                status=ser.validated_data["status"],
                actor=request.user,
                allow_closed=ser.validated_data.get("allow_closed", False),
            )
        except (TransitionError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=400)
        data = ExpenseSerializer(expense, context={"request": request}).data
        data["warnings"] = warnings
        return Response(data)

    @action(detail=False, methods=["post"], url_path="bulk-update")
    def bulk_update(self, request):
        ser = BulkUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        qs = self.get_queryset().filter(id__in=data["ids"])
        updated = 0
        errors = []
        status_obj = None
        if data.get("status"):
            status_obj = ExpenseStatus.objects.filter(id=data["status"]).first()
            if not status_obj:
                return Response({"detail": "Estado inválido"}, status=400)
        efe = None
        if "efe_account" in data and data["efe_account"]:
            efe = FinancialAccount.objects.filter(
                id=data["efe_account"], is_leaf=True
            ).first()
            if not efe:
                return Response({"detail": "Cuenta EFE inválida"}, status=400)

        for expense in qs:
            try:
                if efe:
                    expense.efe_account = efe
                if "attribution" in data:
                    expense.attribution = data["attribution"]
                if "checked" in data:
                    expense.checked = data["checked"]
                if "iva_already_discounted" in data:
                    expense.iva_already_discounted = data["iva_already_discounted"]
                expense.save()
                if status_obj:
                    transition_expense(expense, status=status_obj, actor=request.user)
                elif expense.status.feeds_efe:
                    regenerate_amortization(expense)
                updated += 1
            except (TransitionError, ValueError) as exc:
                errors.append({"id": str(expense.id), "detail": str(exc)})
        return Response({"updated": updated, "errors": errors})

    @action(detail=True, methods=["post"])
    def reconcile(self, request, pk=None):
        expense = self.get_object()
        ser = ReconcileSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        movement = BankMovement.objects.filter(id=ser.validated_data["bank_movement"]).first()
        if not movement:
            return Response({"detail": "Movimiento no encontrado"}, status=404)
        try:
            expense = reconcile_expense(expense, movement, actor=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(ExpenseSerializer(expense, context={"request": request}).data)

    @action(detail=True, methods=["get"], url_path="suggest-movements")
    def suggest_movements(self, request, pk=None):
        expense = self.get_object()
        movs = suggest_movements(expense)
        return Response(
            [
                {
                    "id": str(m.id),
                    "bank": m.bank.name,
                    "date": m.date.isoformat(),
                    "value": str(m.value),
                    "concept": m.concept,
                    "status": m.status,
                }
                for m in movs
            ]
        )

    @action(detail=False, methods=["get", "post"])
    def payables(self, request):
        """Cola Notion-like: reembolsos + cuentas por pagar."""
        if request.method == "POST":
            ser = CreatePayableSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            data = ser.validated_data
            try:
                expense = create_payable(
                    kind=data["kind"],
                    title=data["title"],
                    amount=data["amount"],
                    expense_date=data["expense_date"],
                    concept=data.get("concept") or "",
                    bank_account_id=data.get("bank_account"),
                    efe_account_id=data.get("efe_account"),
                    responsible_id=data.get("responsible"),
                    actor=request.user,
                )
            except TransitionError as exc:
                return Response({"detail": str(exc)}, status=400)
            expense = self.get_queryset().get(pk=expense.pk)
            return Response(
                ExpenseSerializer(expense, context={"request": request}).data,
                status=201,
            )

        qs = self.filter_queryset(
            self.get_queryset().filter(
                status__key__in=["REEMBOLSOS_POR_PAGAR", "CUENTAS_POR_PAGAR"]
            )
        )
        kind = request.query_params.get("kind")
        if kind == "reembolso":
            qs = qs.filter(status__key="REEMBOLSOS_POR_PAGAR")
        elif kind == "cuenta":
            qs = qs.filter(status__key="CUENTAS_POR_PAGAR")

        reembolsos = qs.filter(status__key="REEMBOLSOS_POR_PAGAR")
        cuentas = qs.filter(status__key="CUENTAS_POR_PAGAR")
        ser_ctx = {"request": request}
        return Response(
            {
                "reembolsos": {
                    "count": reembolsos.count(),
                    "total_amount": str(reembolsos.aggregate(s=Sum("amount"))["s"] or 0),
                    "results": ExpenseSerializer(
                        reembolsos[:200], many=True, context=ser_ctx
                    ).data,
                },
                "cuentas": {
                    "count": cuentas.count(),
                    "total_amount": str(cuentas.aggregate(s=Sum("amount"))["s"] or 0),
                    "results": ExpenseSerializer(
                        cuentas[:200], many=True, context=ser_ctx
                    ).data,
                },
            }
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="mark-paid",
        parser_classes=[MultiPartParser, FormParser],
    )
    def mark_paid(self, request, pk=None):
        expense = self.get_object()
        # Multipart fields come as strings; coerce booleans.
        payload = {
            "payment_date": request.data.get("payment_date"),
            "bank_account": request.data.get("bank_account") or None,
            "efe_account": request.data.get("efe_account") or None,
            "register_in_efe": str(request.data.get("register_in_efe", "")).lower()
            in {"1", "true", "yes", "on"},
        }
        ser = MarkPaidSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        try:
            expense, warnings = mark_payable_paid(
                expense,
                payment_date=ser.validated_data["payment_date"],
                bank_account_id=ser.validated_data.get("bank_account"),
                efe_account_id=ser.validated_data.get("efe_account"),
                register_in_efe=ser.validated_data.get("register_in_efe", False),
                payment_proof=request.FILES.get("payment_proof"),
                provider_invoice=request.FILES.get("provider_invoice"),
                actor=request.user,
            )
        except TransitionError as exc:
            return Response({"detail": str(exc)}, status=400)
        expense = self.get_queryset().get(pk=expense.pk)
        data = ExpenseSerializer(expense, context={"request": request}).data
        data["warnings"] = warnings
        return Response(data)

    @action(detail=False, methods=["get"])
    def reimbursements(self, request):
        qs = self.filter_queryset(
            self.get_queryset().filter(status__key="REEMBOLSOS_POR_PAGAR")
        )
        total = qs.aggregate(s=Sum("amount"))["s"] or 0
        ser = ExpenseSerializer(qs[:500], many=True, context={"request": request})
        return Response({"total_amount": str(total), "results": ser.data, "count": qs.count()})

    @action(detail=False, methods=["get"])
    def iva(self, request):
        qs = self.filter_queryset(
            self.get_queryset().filter(iva_discountable__isnull=False).exclude(iva_discountable=0)
        )
        pending = request.query_params.get("pending")
        if pending in {"1", "true", "True"}:
            qs = qs.filter(iva_already_discounted=False)
        total = qs.aggregate(s=Sum("iva_discountable"))["s"] or 0
        ser = ExpenseSerializer(qs[:500], many=True, context={"request": request})
        return Response({"total_iva": str(total), "results": ser.data, "count": qs.count()})

    @action(
        detail=True,
        methods=["post"],
        url_path="attachments",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_attachment(self, request, pk=None):
        expense = self.get_object()
        upload = request.FILES.get("file")
        kind = request.data.get("kind") or AttachmentKind.OTHER
        if kind not in AttachmentKind.values:
            return Response({"detail": "kind inválido"}, status=400)
        if not upload:
            return Response({"detail": "Archivo requerido"}, status=400)
        if upload.size > MAX_UPLOAD_BYTES:
            return Response({"detail": "Archivo supera 12MB"}, status=400)
        mime = getattr(upload, "content_type", "") or ""
        if mime and mime not in ALLOWED_MIME:
            return Response(
                {"detail": f"Tipo no permitido: {mime}. Usa JPG/PNG/PDF."},
                status=400,
            )
        att = ExpenseAttachment.objects.create(
            expense=expense,
            kind=kind,
            file=upload,
            filename=upload.name[:255],
            mime_type=mime,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )
        return Response(
            ExpenseAttachmentSerializer(att).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path=r"attachments/(?P<att_id>[0-9a-f-]+)/download",
    )
    def download_attachment(self, request, pk=None, att_id=None):
        expense = self.get_object()
        att = expense.attachments.filter(id=att_id).first()
        if not att or not att.file:
            raise Http404
        return FileResponse(
            att.file.open("rb"),
            as_attachment=True,
            filename=att.filename or att.file.name,
            content_type=att.mime_type or "application/octet-stream",
        )


class SeedExpensesView(APIView):
    permission_classes = [IsModuleRole]
    permission_module = "expenses"
    permission_crud = "u"

    def post(self, request):
        result = seed_expense_statuses(actor=request.user)
        return Response(result)
