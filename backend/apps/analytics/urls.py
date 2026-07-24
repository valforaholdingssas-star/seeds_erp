from django.urls import path

from apps.analytics.views import (
    AnalyticsOverviewView,
    BigQuerySyncView,
    HomeOverviewView,
    SalesByChannelView,
    SalesByCityView,
    SalesBySellerView,
    SalesSummaryView,
    SalesTimeseriesView,
    SalesWeekdayView,
    SalesYearCompareView,
)

urlpatterns = [
    path("analytics/sales/summary/", SalesSummaryView.as_view(), name="analytics-summary"),
    path("analytics/sales/by-channel/", SalesByChannelView.as_view(), name="analytics-by-channel"),
    path("analytics/sales/by-seller/", SalesBySellerView.as_view(), name="analytics-by-seller"),
    path("analytics/sales/by-city/", SalesByCityView.as_view(), name="analytics-by-city"),
    path("analytics/sales/timeseries/", SalesTimeseriesView.as_view(), name="analytics-timeseries"),
    path("analytics/sales/weekday/", SalesWeekdayView.as_view(), name="analytics-weekday"),
    path("analytics/sales/year-compare/", SalesYearCompareView.as_view(), name="analytics-year"),
    path("analytics/sales/overview/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
    path("analytics/home/", HomeOverviewView.as_view(), name="analytics-home"),
    path("analytics/bigquery/sync/", BigQuerySyncView.as_view(), name="analytics-bq-sync"),
]
