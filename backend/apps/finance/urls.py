from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.finance.views import (
    AccountingAccountViewSet,
    BankImportBatchViewSet,
    BankImportView,
    BankMovementViewSet,
    BankViewSet,
    ClassificationKpiView,
    ClassificationRuleViewSet,
    EfeBudgetViewSet,
    EfeCloseMonthView,
    EfeDrilldownView,
    EfeView,
    FinancialAccountViewSet,
    IncomeAuditView,
    SeedFinanceView,
)

router = DefaultRouter()
router.register("finance/accounts/efe", FinancialAccountViewSet, basename="finance-efe")
router.register("finance/accounts/puc", AccountingAccountViewSet, basename="finance-puc")
router.register("finance/banks", BankViewSet, basename="finance-banks")
router.register(
    "finance/classification-rules",
    ClassificationRuleViewSet,
    basename="finance-rules",
)
router.register("finance/movements", BankMovementViewSet, basename="finance-movements")
router.register(
    "finance/import-batches",
    BankImportBatchViewSet,
    basename="finance-batches",
)
router.register("finance/efe/budgets", EfeBudgetViewSet, basename="finance-budgets")

urlpatterns = [
    path(
        "finance/bank-import/<str:bank_slug>/",
        BankImportView.as_view(),
        name="finance-bank-import",
    ),
    path(
        "finance/classification/kpi/",
        ClassificationKpiView.as_view(),
        name="finance-class-kpi",
    ),
    path("finance/efe/", EfeView.as_view(), name="finance-efe-matrix"),
    path(
        "finance/efe/line/<str:code>/drilldown/",
        EfeDrilldownView.as_view(),
        name="finance-efe-drill",
    ),
    path(
        "finance/efe/close-month/",
        EfeCloseMonthView.as_view(),
        name="finance-efe-close",
    ),
    path(
        "finance/audit/reports-vs-banks/",
        IncomeAuditView.as_view(),
        name="finance-audit",
    ),
    path(
        "finance/audit/chart/",
        IncomeAuditView.as_view(),
        name="finance-audit-chart",
    ),
    path("finance/seed/", SeedFinanceView.as_view(), name="finance-seed"),
    path("", include(router.urls)),
]
