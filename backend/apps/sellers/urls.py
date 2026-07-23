from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.sellers.views import VendedorViewSet

router = DefaultRouter()
router.register("sellers", VendedorViewSet, basename="sellers")

urlpatterns = [
    path("", include(router.urls)),
]
