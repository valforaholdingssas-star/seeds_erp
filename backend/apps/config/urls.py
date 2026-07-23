from django.urls import path

from apps.config.views import (
    ConfigAuditView,
    ConfigGroupView,
    ConfigListView,
    ConfigTestView,
    IntegrationStatusView,
)

urlpatterns = [
    path("config/", ConfigListView.as_view(), name="config-list"),
    path("config/audit/", ConfigAuditView.as_view(), name="config-audit"),
    path(
        "config/integration-status/",
        IntegrationStatusView.as_view(),
        name="config-integration-status",
    ),
    path("config/<str:group>/", ConfigGroupView.as_view(), name="config-group"),
    path("config/<str:group>/test/", ConfigTestView.as_view(), name="config-test"),
]
