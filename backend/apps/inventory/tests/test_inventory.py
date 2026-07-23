import pytest
from rest_framework.test import APIClient

from apps.geo.models import GeoCatalog
from apps.geo.services import normalize_text
from apps.inventory.models import KardexEntry, Product
from apps.inventory.services import discount_stock_for_shipment
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
        email="inv-admin@test.seeds",
        password="testpass123",
        full_name="Inv Admin",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def products(db):
    d = Product.objects.create(
        sku="GEN-DORADO",
        name="Dorados genérico",
        color="DORADO",
        is_generic=True,
        stock=20,
        reorder_level=5,
    )
    p = Product.objects.create(
        sku="GEN-PLATEADO",
        name="Plateados genérico",
        color="PLATEADO",
        is_generic=True,
        stock=15,
        reorder_level=5,
    )
    return d, p


@pytest.fixture
def ready_shipment(db, products):
    ensure_system_vendors()
    from apps.sellers.models import Vendedor

    GeoCatalog.objects.create(
        municipality="Bogotá",
        municipality_code="11001000",
        department="Bogotá D.C.",
        department_iso="DC",
        search=normalize_text("Bogotá"),
    )
    seller = Vendedor.objects.get(name="ECOMMERCE")
    sale = ConsolidatedSale.objects.create(
        source=SaleSource.ECOMMERCE,
        external_id="INV-1",
        seller=seller,
        customer_name="Cliente Inv",
        address_raw="Calle 1 #2-3",
        city_raw="Bogotá",
        total_value="50000",
        status="processing",
        state=SaleState.ACTIVE,
        income_source="E-COMMERCE",
        requires_shipping=True,
    )
    SaleItem.objects.create(sale=sale, color="DORADO", quantity=3)
    SaleItem.objects.create(sale=sale, color="PLATEADO", quantity=2)
    shipment = Shipment.objects.get(sale=sale)
    format_shipment(shipment)
    generate_shipment_guide(shipment.id)
    shipment.refresh_from_db()
    assert shipment.status == ShipmentStatus.LISTO_PARA_ENVIAR
    return shipment


@pytest.mark.django_db
def test_discount_on_dispatch_idempotent(ready_shipment, products):
    d, p = products
    mark_shipments_sent([ready_shipment.id])
    d.refresh_from_db()
    p.refresh_from_db()
    assert d.stock == 17
    assert p.stock == 13
    assert KardexEntry.objects.filter(ref_id=str(ready_shipment.id), movement="OUT").count() == 2

    mark_shipments_sent([ready_shipment.id])
    d.refresh_from_db()
    assert d.stock == 17

    discount_stock_for_shipment(ready_shipment)
    d.refresh_from_db()
    assert d.stock == 17


@pytest.mark.django_db
def test_manual_entry_api(api, admin_user, products):
    d, _ = products
    api.force_authenticate(user=admin_user)
    res = api.post(
        "/api/v1/inventory/entries/",
        {
            "product_id": str(d.id),
            "movement": "IN",
            "quantity": "10",
            "reason": "PURCHASE",
            "notes": "Compra test",
        },
        format="json",
    )
    assert res.status_code == 201
    d.refresh_from_db()
    assert d.stock == 30
    listed = api.get("/api/v1/inventory/products/")
    assert listed.status_code == 200
