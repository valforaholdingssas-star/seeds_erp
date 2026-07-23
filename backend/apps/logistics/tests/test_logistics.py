import pytest
from rest_framework.test import APIClient

from apps.geo.models import GeoCatalog
from apps.geo.services import normalize_text
from apps.logistics.models import Shipment, ShipmentStatus
from apps.logistics.services.formatting import format_shipment
from apps.logistics.services.shipments import generate_shipment_guide, mark_shipments_sent
from apps.sales.models import ConsolidatedSale, SaleItem, SaleSource, SaleState
from apps.sellers.services import ensure_system_vendors
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="logistics-admin@test.seeds",
        password="testpass123",
        full_name="Logistics Admin",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def bogota(db):
    return GeoCatalog.objects.create(
        municipality="Bogotá",
        municipality_code="11001000",
        department="Bogotá D.C.",
        department_iso="DC",
        search=normalize_text("Bogotá"),
    )


@pytest.fixture
def sale_with_shipment(db, bogota):
    ensure_system_vendors()
    from apps.sellers.models import Vendedor

    seller = Vendedor.objects.get(name="ECOMMERCE")
    sale = ConsolidatedSale.objects.create(
        source=SaleSource.ECOMMERCE,
        external_id="LOG-100",
        seller=seller,
        customer_name="Cliente Logística",
        email="cli@ex.com",
        phone="3001112233",
        id_number="1010",
        address_raw="Calle 100 #15-20",
        city_raw="Bogotá",
        state_raw="DC",
        total_value="119000",
        status="processing",
        state=SaleState.ACTIVE,
        income_source="E-COMMERCE",
        requires_shipping=True,
    )
    SaleItem.objects.create(sale=sale, color="DORADO", quantity=2)
    SaleItem.objects.create(sale=sale, color="PLATEADO", quantity=1)
    # signal should create shipment
    shipment = Shipment.objects.get(sale=sale)
    return sale, shipment


@pytest.mark.django_db
def test_format_and_generate_mock(sale_with_shipment):
    sale, shipment = sale_with_shipment
    format_shipment(shipment)
    shipment.refresh_from_db()
    assert shipment.geo_city_id
    assert "cll" in shipment.address_formatted
    assert not shipment.do_not_ship

    generate_shipment_guide(shipment.id)
    shipment.refresh_from_db()
    assert shipment.status == ShipmentStatus.LISTO_PARA_ENVIAR
    assert shipment.tracking_number.startswith("MOCK")
    sale.refresh_from_db()
    assert sale.amount_shipping == shipment.shipping_cost


@pytest.mark.django_db
def test_blocked_city_marks_revisar(sale_with_shipment):
    _, shipment = sale_with_shipment
    shipment.city_mirror = "Domicilio"
    shipment.save()
    format_shipment(shipment)
    shipment.refresh_from_db()
    assert shipment.do_not_ship
    assert shipment.status == ShipmentStatus.REVISAR


@pytest.mark.django_db
def test_dispatch_mark_sent_api(api, admin_user, sale_with_shipment):
    _, shipment = sale_with_shipment
    format_shipment(shipment)
    generate_shipment_guide(shipment.id)
    shipment.refresh_from_db()

    api.force_authenticate(user=admin_user)
    res = api.post(
        "/api/v1/logistics/dispatch/mark-sent/",
        {"ids": [str(shipment.id)]},
        format="json",
    )
    assert res.status_code == 200
    assert res.data["updated"] == 1
    shipment.refresh_from_db()
    assert shipment.status == ShipmentStatus.ENVIADO

    board = api.get("/api/v1/logistics/shipments/")
    assert board.status_code == 200
    results = board.data["results"] if "results" in board.data else board.data
    assert all(r["id"] != str(shipment.id) for r in results)


@pytest.mark.django_db
def test_dispatch_pack_summary(api, admin_user, sale_with_shipment):
    sale, shipment = sale_with_shipment
    SaleItem.objects.filter(sale=sale, color="DORADO").update(product_name="Kit Seeds")
    format_shipment(shipment)
    generate_shipment_guide(shipment.id)

    api.force_authenticate(user=admin_user)
    empty = api.get("/api/v1/logistics/dispatch/pack-summary/", {"sent": "1"})
    assert empty.status_code == 200
    assert empty.data["orders"] == 0

    res = api.get("/api/v1/logistics/dispatch/pack-summary/")
    assert res.status_code == 200
    assert res.data["orders"] == 1
    assert res.data["total_units"] == 3
    assert res.data["by_color"]["DORADO"] == 2
    assert res.data["by_color"]["PLATEADO"] == 1
    labels = [p["label"] for p in res.data["products"]]
    assert any("Kit Seeds" in lab for lab in labels)
    assert any(p["units"] == 2 for p in res.data["products"] if p["color"] == "DORADO")
