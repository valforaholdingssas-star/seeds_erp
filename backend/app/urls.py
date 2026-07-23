from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.views import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.config.urls")),
    path("api/v1/", include("apps.geo.urls")),
    path("api/v1/", include("apps.integrations.urls")),
    path("api/v1/", include("apps.sellers.urls")),
    path("api/v1/", include("apps.sales.urls")),
    path("api/v1/", include("apps.logistics.urls")),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.accounting.urls")),
    path("api/v1/", include("apps.leads.urls")),
    path("api/v1/", include("apps.ai.urls")),
    path("api/v1/", include("apps.analytics.urls")),
]
