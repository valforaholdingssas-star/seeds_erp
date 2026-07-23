from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.integrations.views import RawWebhookEventViewSet

router = DefaultRouter()
router.register("integrations/events", RawWebhookEventViewSet, basename="integration-events")

urlpatterns = [
    path("", include(router.urls)),
]
