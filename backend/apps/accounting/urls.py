from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounting.views import (
    CustomerViewSet,
    InvoiceViewSet,
    IvaSummaryView,
    RefundViewSet,
)

router = DefaultRouter()
router.register("accounting/customers", CustomerViewSet, basename="customers")
router.register("accounting/invoices", InvoiceViewSet, basename="invoices")
router.register("accounting/refunds", RefundViewSet, basename="refunds")

urlpatterns = [
    path("accounting/iva/summary/", IvaSummaryView.as_view(), name="iva-summary"),
    path("", include(router.urls)),
]
