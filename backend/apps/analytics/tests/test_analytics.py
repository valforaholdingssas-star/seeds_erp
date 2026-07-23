import pytest
from rest_framework.test import APIClient

from apps.sales.models import ConsolidatedSale, SaleSource, SaleState
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin-analytics@test.seeds",
        password="testpass123",
        full_name="Admin Analytics",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
def test_analytics_overview(api, admin_user):
    ConsolidatedSale.objects.create(
        source=SaleSource.FERIAS,
        external_id="AN-1",
        customer_name="Test",
        total_value="100000",
        state=SaleState.ACTIVE,
        status="processing",
        city_raw="Bogotá",
    )
    api.force_authenticate(user=admin_user)
    res = api.get("/api/v1/analytics/sales/overview/")
    assert res.status_code == 200
    assert "kpis" in res.data["summary"]
    assert res.data["summary"]["kpis"]["orders"] >= 1

    ch = api.get("/api/v1/analytics/sales/by-channel/")
    assert ch.status_code == 200
    assert ch.data["series"]
