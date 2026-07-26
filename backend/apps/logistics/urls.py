from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.logistics.views import (
    BatchJobViewSet,
    DispatchLabelsPdfView,
    DispatchListView,
    DispatchMarkSentView,
    DispatchPackSummaryView,
    EnviaPaymentsView,
    ShipmentViewSet,
)

router = DefaultRouter()
router.register("logistics/shipments", ShipmentViewSet, basename="shipments")
router.register("logistics/batches", BatchJobViewSet, basename="batches")

urlpatterns = [
    path("logistics/dispatch/", DispatchListView.as_view(), name="dispatch-list"),
    path(
        "logistics/dispatch/pack-summary/",
        DispatchPackSummaryView.as_view(),
        name="dispatch-pack-summary",
    ),
    path(
        "logistics/dispatch/mark-sent/",
        DispatchMarkSentView.as_view(),
        name="dispatch-mark-sent",
    ),
    path(
        "logistics/dispatch/labels-pdf/",
        DispatchLabelsPdfView.as_view(),
        name="dispatch-labels-pdf",
    ),
    path(
        "logistics/envia-payments/",
        EnviaPaymentsView.as_view(),
        name="envia-payments",
    ),
    path("", include(router.urls)),
]
