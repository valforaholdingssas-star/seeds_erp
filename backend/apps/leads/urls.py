from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.leads.views import LeadViewSet

router = DefaultRouter()
router.register("leads", LeadViewSet, basename="leads")

urlpatterns = [
    path("", include(router.urls)),
]
