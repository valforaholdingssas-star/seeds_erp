from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.dashboard.views import (
    ControlIndicatorViewSet,
    DashboardIndicatorDetailView,
    DashboardOverviewView,
    SeedDashboardView,
)

router = DefaultRouter()
router.register(
    r"dashboard/indicators", ControlIndicatorViewSet, basename="control-indicator"
)

urlpatterns = [
    path("dashboard/", DashboardOverviewView.as_view(), name="dashboard-overview"),
    path("dashboard/seed/", SeedDashboardView.as_view(), name="dashboard-seed"),
    path("", include(router.urls)),
    path(
        "dashboard/<str:key>/",
        DashboardIndicatorDetailView.as_view(),
        name="dashboard-indicator",
    ),
]
