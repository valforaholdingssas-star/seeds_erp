from django.urls import path

from apps.config.views import (
    ConfigAuditView,
    ConfigGroupView,
    ConfigListView,
    ConfigTestView,
    IntegrationStatusView,
    SyncInboundUrlsView,
)

urlpatterns = [
    path("config/", ConfigListView.as_view(), name="config-list"),
    path("config/audit/", ConfigAuditView.as_view(), name="config-audit"),
    path(
        "config/integration-status/",
        IntegrationStatusView.as_view(),
        name="config-integration-status",
    ),
    path(
        "config/sync-inbound-urls/",
        SyncInboundUrlsView.as_view(),
        name="config-sync-inbound-urls",
    ),
    path("config/<str:group>/", ConfigGroupView.as_view(), name="config-group"),
    path("config/<str:group>/test/", ConfigTestView.as_view(), name="config-test"),
]
