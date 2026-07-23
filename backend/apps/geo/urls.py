from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.geo.views import GeoCatalogViewSet

router = DefaultRouter()
router.register("geo/catalog", GeoCatalogViewSet, basename="geo-catalog")

urlpatterns = [
    path("", include(router.urls)),
]
