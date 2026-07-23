import pytest
from rest_framework.test import APIClient

from apps.logistics.models import Shipment
from apps.sales.models import ConsolidatedSale, FulfillmentType, SaleSource, SaleState
from apps.sellers.services import ensure_system_vendors
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="ful-admin@test.seeds",
        password="testpass123",
        full_name="Fulfill Admin",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
def test_oficina_sale_creates_no_shipment(api, admin_user):
    ensure_system_vendors()
    api.force_authenticate(user=admin_user)
    res = api.post(
        "/api/v1/sales/manual/",
        {
            "customer_name": "Cliente Oficina",
            "id_number": "999001",
            "total_value": "189000",
            "qty_dorados": 1,
            "commercial_raw": "VENDEDORA 1",
            "fulfillment_type": "OFICINA",
            "requires_shipping": False,
        },
        format="json",
    )
    # may 400 if VENDEDORA 1 missing — create via resolve
    if res.status_code == 400:
        from apps.sellers.models import Vendedor

        Vendedor.objects.create(name="VENDEDORA 1", active=True)
        res = api.post(
            "/api/v1/sales/manual/",
            {
                "customer_name": "Cliente Oficina",
                "id_number": "999001",
                "total_value": "189000",
                "qty_dorados": 1,
                "commercial_raw": "VENDEDORA 1",
                "fulfillment_type": "OFICINA",
            },
            format="json",
        )
    assert res.status_code == 201, res.data
    sale_id = res.data["sale"]["id"]
    sale = ConsolidatedSale.objects.get(id=sale_id)
    assert sale.fulfillment_type == FulfillmentType.OFICINA
    assert sale.requires_shipping is False
    assert not Shipment.objects.filter(sale=sale).exists()


@pytest.mark.django_db
def test_switch_envia_to_domicilio_removes_pending_shipment(api, admin_user):
    ensure_system_vendors()
    from apps.sellers.models import Vendedor

    seller = Vendedor.objects.get(name="ECOMMERCE")
    sale = ConsolidatedSale.objects.create(
        source=SaleSource.MANUAL,
        external_id="FUL-ENV-1",
        seller=seller,
        customer_name="Ana",
        address_raw="Calle 1",
        city_raw="Bogotá",
        total_value="100000",
        status="completed",
        state=SaleState.ACTIVE,
        requires_shipping=True,
        fulfillment_type=FulfillmentType.ENVIA,
    )
    assert Shipment.objects.filter(sale=sale).exists()

    api.force_authenticate(user=admin_user)
    patch = api.patch(
        f"/api/v1/sales/{sale.id}/",
        {"fulfillment_type": "DOMICILIO"},
        format="json",
    )
    assert patch.status_code == 200, patch.data
    sale.refresh_from_db()
    assert sale.fulfillment_type == FulfillmentType.DOMICILIO
    assert sale.requires_shipping is False
    assert not Shipment.objects.filter(sale=sale).exists()
