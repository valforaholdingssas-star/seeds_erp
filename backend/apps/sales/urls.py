from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.sales.views import (
    ConsolidatedSaleViewSet,
    EcommerceResyncView,
    FailedEcommerceDetailView,
    FailedEcommerceListView,
    FeriaSaleCreateView,
    KommoWebhookView,
    ManualSaleCreateView,
    SalesGoalsView,
    ShopifyResyncView,
    ShopifyWebhookView,
    WooCommerceWebhookView,
)
from apps.sales.payment_views import PaymentMethodViewSet
from apps.sales.pack_views import ProductPackRuleViewSet

router = DefaultRouter()
router.register("sales", ConsolidatedSaleViewSet, basename="sales")
router.register("payment-methods", PaymentMethodViewSet, basename="payment-methods")
router.register("pack-rules", ProductPackRuleViewSet, basename="pack-rules")

urlpatterns = [
    path("sales/ferias/", FeriaSaleCreateView.as_view(), name="sales-ferias"),
    path("sales/manual/", ManualSaleCreateView.as_view(), name="sales-manual"),
    path("sales/ecommerce/resync/", EcommerceResyncView.as_view(), name="sales-woo-resync"),
    path("sales/shopify/resync/", ShopifyResyncView.as_view(), name="sales-shopify-resync"),
    path(
        "sales/failed-ecommerce/",
        FailedEcommerceListView.as_view(),
        name="sales-failed-ecommerce",
    ),
    path(
        "sales/failed-ecommerce/<uuid:pk>/",
        FailedEcommerceDetailView.as_view(),
        name="sales-failed-ecommerce-detail",
    ),
    path("sales/goals/", SalesGoalsView.as_view(), name="sales-goals"),
    path(
        "webhooks/woocommerce/order-created/",
        WooCommerceWebhookView.as_view(),
        {"event": "created"},
        name="webhook-woo-created",
    ),
    path(
        "webhooks/woocommerce/order-updated/",
        WooCommerceWebhookView.as_view(),
        {"event": "updated"},
        name="webhook-woo-updated",
    ),
    path(
        "webhooks/shopify/orders/",
        ShopifyWebhookView.as_view(),
        name="webhook-shopify-orders",
    ),
    path(
        "webhooks/kommo/lead-status-changed/",
        KommoWebhookView.as_view(),
        name="webhook-kommo",
    ),
    path("", include(router.urls)),
]
