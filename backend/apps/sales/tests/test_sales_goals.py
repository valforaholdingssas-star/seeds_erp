import pytest
from rest_framework.test import APIClient

from apps.sellers.models import SellerMonthlyGoal, Vendedor
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def ventas_user(db):
    return User.objects.create_user(
        email="goals-ventas@test.seeds",
        password="testpass123",
        full_name="Goals Ventas",
        role=Role.VENTAS,
    )


@pytest.mark.django_db
def test_sales_goals_matrix_upsert(api, ventas_user):
    seller = Vendedor.objects.create(name="COMERCIAL TEST", active=True, is_system=False)
    api.force_authenticate(user=ventas_user)

    listed = api.get("/api/v1/sales/goals/?year=2026")
    assert listed.status_code == 200
    assert listed.data["year"] == 2026
    assert any(r["seller_id"] == str(seller.id) for r in listed.data["sellers"])

    saved = api.put(
        "/api/v1/sales/goals/",
        {
            "year": 2026,
            "items": [
                {"seller_id": str(seller.id), "month": 7, "amount": "15000000"},
                {"seller_id": str(seller.id), "month": 8, "amount": "16000000"},
            ],
        },
        format="json",
    )
    assert saved.status_code == 200
    assert saved.data["saved"] == 2
    assert SellerMonthlyGoal.objects.filter(seller=seller, year=2026).count() == 2

    row = next(r for r in saved.data["sellers"] if r["seller_id"] == str(seller.id))
    assert row["months"]["7"] == "15000000.00"
    assert float(row["year_total"]) == 31000000.0
