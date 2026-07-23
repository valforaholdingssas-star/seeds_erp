from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.ai.views import AgentAskView, DocumentViewSet

router = DefaultRouter()
router.register("ai/documents", DocumentViewSet, basename="ai-documents")

urlpatterns = [
    path("ai/ask/", AgentAskView.as_view(), name="ai-ask"),
    path("", include(router.urls)),
]
