from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services import (
    by_channel,
    by_city,
    by_seller,
    home_overview,
    sales_summary,
    timeseries,
    weekday_bars,
    year_comparison,
)
from apps.analytics.services.metrics import _parse_date
from apps.users.permissions import IsModuleRole


class AnalyticsBaseView(APIView):
    def get_permissions(self):
        self.module_roles = ["VENTAS", "SUPERVISOR", "VIEWER", "CONTABILIDAD", "LOGISTICA"]
        return [IsModuleRole()]

    def filters(self, request):
        return {
            "date_from": _parse_date(request.query_params.get("from")),
            "date_to": _parse_date(request.query_params.get("to")),
            "source": request.query_params.get("source") or None,
            "seller": request.query_params.get("seller") or None,
            "city": request.query_params.get("city") or None,
        }


class SalesSummaryView(AnalyticsBaseView):
    def get(self, request):
        f = self.filters(request)
        compare = request.query_params.get("compare", "prev") != "none"
        return Response(sales_summary(**f, compare=compare))


class SalesByChannelView(AnalyticsBaseView):
    def get(self, request):
        return Response(by_channel(**self.filters(request)))


class SalesBySellerView(AnalyticsBaseView):
    def get(self, request):
        return Response(by_seller(**self.filters(request)))


class SalesByCityView(AnalyticsBaseView):
    def get(self, request):
        f = self.filters(request)
        scope = request.query_params.get("scope") or "month"
        return Response(by_city(**f, scope=scope))


class SalesTimeseriesView(AnalyticsBaseView):
    def get(self, request):
        f = self.filters(request)
        gran = request.query_params.get("granularity") or "day"
        return Response(timeseries(**f, granularity=gran))


class SalesWeekdayView(AnalyticsBaseView):
    def get(self, request):
        return Response(weekday_bars(**self.filters(request)))


class SalesYearCompareView(AnalyticsBaseView):
    def get(self, request):
        f = self.filters(request)
        return Response(
            year_comparison(source=f.get("source"), seller=f.get("seller"), city=f.get("city"))
        )


class AnalyticsOverviewView(AnalyticsBaseView):
    """Bundle for the metrics dashboard in one round-trip."""

    def get(self, request):
        f = self.filters(request)
        return Response(
            {
                "summary": sales_summary(**f, compare=True),
                "by_channel": by_channel(**f),
                "by_seller": by_seller(**f),
                "by_city": by_city(**f, scope="month"),
                "timeseries": timeseries(**f, granularity="day"),
                "weekday": weekday_bars(**f),
                "year": year_comparison(
                    source=f.get("source"), seller=f.get("seller"), city=f.get("city")
                ),
            }
        )


class HomeOverviewView(AnalyticsBaseView):
    """Operational KPIs for Inicio."""

    def get(self, request):
        return Response(home_overview())
