from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.inventory.views import KardexViewSet, ManualEntryView, MaterialViewSet, ProductViewSet

router = DefaultRouter()
router.register("inventory/products", ProductViewSet, basename="products")
router.register("inventory/materials", MaterialViewSet, basename="materials")
router.register("inventory/kardex", KardexViewSet, basename="kardex")

urlpatterns = [
    path("inventory/entries/", ManualEntryView.as_view(), name="inventory-entries"),
    path("", include(router.urls)),
]
