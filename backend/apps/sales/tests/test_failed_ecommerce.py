import pytest
from rest_framework.test import APIClient

from apps.sales.models import EcommerceSale, FollowUpStatus, ShopifySale
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def ventas_user(db):
    return User.objects.create_user(
        email="ventas-failed@test.seeds",
        password="testpass123",
        full_name="Vendedora Test",
        role=Role.VENTAS,
    )


@pytest.mark.django_db
def test_failed_ecommerce_list_and_mark_contacted(api, ventas_user):
    pending = EcommerceSale.objects.create(
        external_id="W-FAIL-1",
        status="pending",
        customer_name="Ana Fallida",
        email="ana@example.com",
        phone="3001112233",
        id_number="101010",
        city_raw="Bogotá",
        total_value="99000",
    )
    EcommerceSale.objects.create(
        external_id="W-OK",
        status="processing",
        customer_name="No debe salir",
        total_value="1000",
    )
    ShopifySale.objects.create(
        external_id="S-FAIL-1",
        status="failed",
        customer_name="Shopify Fail",
        phone="3019998877",
        total_value="50000",
    )

    api.force_authenticate(user=ventas_user)
    listed = api.get("/api/v1/sales/failed-ecommerce/")
    assert listed.status_code == 200
    ids = {r["external_id"] for r in listed.data["results"]}
    assert "W-FAIL-1" in ids
    assert "S-FAIL-1" in ids
    assert "W-OK" not in ids

    patch = api.patch(
        f"/api/v1/sales/failed-ecommerce/{pending.id}/",
        {
            "channel": "ECOMMERCE",
            "follow_up_status": FollowUpStatus.CONTACTADO,
            "follow_up_notes": "Llamó, pagará mañana",
            "mark_contacted": True,
        },
        format="json",
    )
    assert patch.status_code == 200
    assert patch.data["follow_up_status"] == FollowUpStatus.CONTACTADO
    assert patch.data["contacted_at"]
    assert "pagará mañana" in patch.data["follow_up_notes"]

    pending.refresh_from_db()
    assert pending.contacted_by_id == ventas_user.id
    assert pending.follow_up_status == FollowUpStatus.CONTACTADO

    contacted = api.get("/api/v1/sales/failed-ecommerce/?contacted=1")
    assert any(r["external_id"] == "W-FAIL-1" for r in contacted.data["results"])
