from __future__ import annotations

from django.db.models import Count, Max, Min
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.models import (
    AccountingAccount,
    Bank,
    BankImportBatch,
    BankMovement,
    ClassificationRule,
    EfeBudget,
    EfeMonthClose,
    FinancialAccount,
)
from apps.finance.serializers import (
    AccountingAccountSerializer,
    BankImportBatchSerializer,
    BankMovementSerializer,
    BankSerializer,
    BulkClassifySerializer,
    ClassificationRuleSerializer,
    EfeBudgetSerializer,
    EfeMonthCloseSerializer,
    FinancialAccountSerializer,
)
from apps.finance.services.audit import build_income_audit
from apps.finance.services.classify import classification_kpi, classify_movements
from apps.finance.services.efe import build_efe, efe_drilldown
from apps.finance.services.import_bank import import_bank_csv
from apps.finance.services.seed import seed_finance
from apps.users.permissions import IsModuleRole


class FinancialAccountViewSet(viewsets.ModelViewSet):
    permission_module = "finance"
    queryset = FinancialAccount.objects.select_related("parent").all()
    serializer_class = FinancialAccountSerializer
    filterset_fields = ["active", "kind", "is_leaf", "parent", "code"]
    search_fields = ["code", "name", "full_label"]
    ordering_fields = ["order", "code", "name"]


class AccountingAccountViewSet(viewsets.ModelViewSet):
    permission_module = "finance"
    queryset = AccountingAccount.objects.all()
    serializer_class = AccountingAccountSerializer
    filterset_fields = ["active", "attribution", "code"]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name"]


class BankViewSet(viewsets.ModelViewSet):
    permission_module = "finance"
    queryset = Bank.objects.all()
    serializer_class = BankSerializer
    filterset_fields = ["active", "kind", "importer", "name"]
    search_fields = ["name", "account_no"]
    ordering_fields = ["name"]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        banks = list(self.filter_queryset(self.get_queryset()))
        bank_ids = [b.id for b in banks]
        last_imports: dict[str, dict] = {}
        coverages: dict[str, dict] = {}
        if bank_ids:
            for bank_id in bank_ids:
                batch = (
                    BankImportBatch.objects.filter(bank_id=bank_id, dry_run=False)
                    .order_by("-created_at")
                    .first()
                )
                if not batch:
                    continue
                date_from, date_to = batch.date_from, batch.date_to
                if date_from is None or date_to is None:
                    agg = batch.movements.aggregate(dmin=Min("date"), dmax=Max("date"))
                    date_from = date_from or agg["dmin"]
                    date_to = date_to or agg["dmax"]
                last_imports[str(bank_id)] = {
                    "batch_id": str(batch.id),
                    "uploaded_at": batch.created_at.isoformat(),
                    "filename": batch.filename,
                    "date_from": date_from.isoformat() if date_from else None,
                    "date_to": date_to.isoformat() if date_to else None,
                    "rows_created": batch.rows_created,
                    "rows_duplicated": batch.rows_duplicated,
                    "rows_total": batch.rows_total,
                }

            cov_rows = (
                BankMovement.objects.filter(bank_id__in=bank_ids)
                .values("bank_id")
                .annotate(
                    date_from=Min("date"),
                    date_to=Max("date"),
                    movements=Count("id"),
                )
            )
            for row in cov_rows:
                coverages[str(row["bank_id"])] = {
                    "date_from": row["date_from"].isoformat() if row["date_from"] else None,
                    "date_to": row["date_to"].isoformat() if row["date_to"] else None,
                    "movements": row["movements"],
                }
        ctx["last_imports"] = last_imports
        ctx["coverages"] = coverages
        return ctx


class ClassificationRuleViewSet(viewsets.ModelViewSet):
    permission_module = "finance"
    queryset = ClassificationRule.objects.select_related(
        "bank", "financial_account", "accounting_account"
    ).all()
    serializer_class = ClassificationRuleSerializer
    filterset_fields = ["active", "bank", "is_interbank", "auto_apply"]
    search_fields = ["name", "concept_contains"]
    ordering_fields = ["priority", "name"]


class BankMovementViewSet(viewsets.ModelViewSet):
    permission_module = "finance"
    queryset = BankMovement.objects.select_related(
        "bank", "financial_account", "accounting_account"
    ).all()
    serializer_class = BankMovementSerializer
    filterset_fields = [
        "status",
        "bank",
        "item",
        "is_interbank",
        "financial_account",
        "accounting_account",
        "alegra_synced",
        "date",
    ]
    search_fields = ["concept", "reference", "comment", "dedupe_hash", "tx_code"]
    ordering_fields = ["date", "value", "created_at", "status"]

    @action(detail=False, methods=["post"], url_path="bulk-classify")
    def bulk_classify(self, request):
        ser = BulkClassifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        n = classify_movements(
            ids=data["ids"],
            financial_account_id=data.get("financial_account"),
            accounting_account_id=data.get("accounting_account"),
            attribution=data.get("attribution", ""),
            is_interbank=data.get("is_interbank"),
            status=data.get("status") or None,
            actor=request.user,
        )
        return Response({"updated": n})


class BankImportBatchViewSet(viewsets.ReadOnlyModelViewSet):
    permission_module = "finance"
    queryset = BankImportBatch.objects.select_related("bank").all()
    serializer_class = BankImportBatchSerializer
    filterset_fields = ["bank", "dry_run"]
    ordering_fields = ["created_at"]


class BankImportView(APIView):
    permission_module = "finance"
    permission_crud = "c"
    permission_classes = [IsModuleRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, bank_slug: str):
        bank = (
            Bank.objects.filter(name__iexact=bank_slug.replace("-", " ")).first()
            or Bank.objects.filter(importer__iexact=bank_slug).first()
            or Bank.objects.filter(id=bank_slug).first()
        )
        if not bank:
            return Response({"detail": f"Banco no encontrado: {bank_slug}"}, status=404)

        dry_run = str(request.data.get("dry_run", "true")).lower() in {
            "1",
            "true",
            "yes",
        }
        upload = request.FILES.get("file")
        text = ""
        filename = ""
        if upload:
            filename = getattr(upload, "name", "") or ""
            text = upload.read().decode("utf-8", errors="replace")
        else:
            text = request.data.get("text") or ""
            filename = request.data.get("filename") or "paste.csv"

        if not text.strip():
            return Response({"detail": "Adjunta un CSV o pega el texto."}, status=400)

        try:
            result = import_bank_csv(
                bank=bank,
                text=text,
                filename=filename,
                dry_run=dry_run,
                actor=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(result, status=200)


class ClassificationKpiView(APIView):
    permission_module = "finance"
    permission_classes = [IsModuleRole]

    def get(self, request):
        now = timezone.localdate()
        year = int(request.query_params.get("year") or now.year)
        month = int(request.query_params.get("month") or now.month)
        return Response(classification_kpi(year=year, month=month))


class EfeView(APIView):
    permission_module = "finance"
    permission_classes = [IsModuleRole]

    def get(self, request):
        year = int(request.query_params.get("year") or timezone.localdate().year)
        return Response(build_efe(year))


class EfeDrilldownView(APIView):
    permission_module = "finance"
    permission_classes = [IsModuleRole]

    def get(self, request, code: str):
        year = int(request.query_params.get("year") or timezone.localdate().year)
        month = int(request.query_params.get("month") or timezone.localdate().month)
        try:
            return Response(efe_drilldown(code=code, year=year, month=month))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=404)


class EfeCloseMonthView(APIView):
    permission_module = "finance"
    permission_crud = "u"
    permission_classes = [IsModuleRole]

    def post(self, request):
        ser = EfeMonthCloseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        year = ser.validated_data["year"]
        month = ser.validated_data["month"]
        kpi = classification_kpi(year=year, month=month)
        force = str(request.data.get("force", "")).lower() in {"1", "true", "yes"}
        if kpi["pending"] and not force:
            return Response(
                {
                    "detail": "Hay movimientos sin clasificar.",
                    "kpi": kpi,
                    "requires_force": True,
                },
                status=400,
            )
        obj, _ = EfeMonthClose.objects.update_or_create(
            year=year,
            month=month,
            defaults={
                "closed_by": request.user,
                "note": ser.validated_data.get("note") or "",
                "unclassified_pct": 100 - kpi["pct_classified"],
            },
        )
        return Response(EfeMonthCloseSerializer(obj).data)


class EfeBudgetViewSet(viewsets.ModelViewSet):
    permission_module = "finance"
    queryset = EfeBudget.objects.select_related("financial_account").all()
    serializer_class = EfeBudgetSerializer
    filterset_fields = ["year", "month", "financial_account"]


class IncomeAuditView(APIView):
    permission_module = "finance"
    permission_classes = [IsModuleRole]

    def get(self, request):
        now = timezone.localdate()
        year = int(request.query_params.get("year") or now.year)
        month = int(request.query_params.get("month") or now.month)
        bank = request.query_params.get("bank") or None
        return Response(build_income_audit(year=year, month=month, bank_name=bank))


class SeedFinanceView(APIView):
    permission_module = "finance"
    permission_crud = "u"
    permission_classes = [IsModuleRole]

    def post(self, request):
        result = seed_finance(actor=request.user)
        return Response(result)
