from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.expenses.views import ExpenseStatusViewSet, ExpenseViewSet, SeedExpensesView

router = DefaultRouter()
router.register(r"expenses/statuses", ExpenseStatusViewSet, basename="expense-status")
router.register(r"expenses", ExpenseViewSet, basename="expense")

urlpatterns = [
    path("expenses/seed/", SeedExpensesView.as_view(), name="expenses-seed"),
    path("", include(router.urls)),
]
