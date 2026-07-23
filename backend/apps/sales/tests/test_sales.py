from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.sales.models import ConsolidatedSale, EcommerceSale, SaleSource, SaleState
from apps.sales.services.normalization import calc_fiscal, promote_to_consolidated
from apps.sales.services.woocommerce import upsert_ecommerce_from_payload
from apps.sellers.services import ensure_system_vendors
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="sales-admin@test.seeds",
        password="testpass123",
        full_name="Sales Admin",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def ventas_user(db):
    return User.objects.create_user(
        email="ventas@test.seeds",
        password="testpass123",
        full_name="Ventas User",
        role=Role.VENTAS,
    )


@pytest.mark.django_db
def test_calc_fiscal_iva_19():
    products, iva, net = calc_fiscal(Decimal("119000"), Decimal("0"))
    assert products == Decimal("119000.00")
    assert iva == Decimal("19000.00")
    assert net == Decimal("100000.00")


@pytest.mark.django_db
def test_woo_upsert_promotes_processing(admin_user):
    ensure_system_vendors()
    payload = {
        "id": 4428,
        "status": "processing",
        "total": "119000",
        "shipping_total": "0",
        "date_created": "2026-07-01T10:00:00",
        "payment_method": "mercado_pago",
        "payment_method_title": "Mercadopago",
        "billing": {
            "first_name": "Ana",
            "last_name": "Pérez",
            "email": "ana@example.com",
            "phone": "3001234567",
            "city": "Bogotá",
            "state": "DC",
            "address_1": "Calle 100",
            "address_2": "Apt 1",
        },
        "meta_data": [{"key": "billing_cedula", "value": "123456"}],
        "line_items": [
            {
                "product_id": 100,
                "name": "Kit Seeds",
                "quantity": 1,
                "meta_data": [{"key": "pa_color", "value": "dorado"}],
            },
            {
                "product_id": 602,
                "name": "Refill automático trimestral (3 kits)",
                "quantity": 1,
                "meta_data": [{"key": "pa_color", "value": "plateados"}],
            },
        ],
    }
    # Without pack rule seed, name contains "3 kits" → ×3
    upsert_ecommerce_from_payload(payload, actor=admin_user)
    assert EcommerceSale.objects.filter(external_id="4428").exists()
    sale = ConsolidatedSale.objects.get(source=SaleSource.ECOMMERCE, external_id="4428")
    assert sale.state == SaleState.ACTIVE
    assert sale.customer_name == "Ana Pérez"
    assert sale.id_number == "123456"
    items = list(sale.items.all())
    qty_d = sum(i.quantity for i in items if i.color == "DORADO")
    qty_p = sum(i.quantity for i in items if i.color == "PLATEADO")
    assert qty_d == 1
    assert qty_p == 3


@pytest.mark.django_db
def test_pending_does_not_consolidate(admin_user):
    ensure_system_vendors()
    upsert_ecommerce_from_payload(
        {
            "id": 99,
            "status": "pending",
            "total": "10000",
            "billing": {"first_name": "X", "last_name": "Y", "city": "Cali"},
            "line_items": [],
        },
        actor=admin_user,
    )
    assert not ConsolidatedSale.objects.filter(external_id="99").exists()
    assert EcommerceSale.objects.filter(external_id="99", status="pending").exists()


@pytest.mark.django_db
def test_feria_and_manual_api(api, ventas_user):
    ensure_system_vendors()
    api.force_authenticate(user=ventas_user)
    feria = api.post(
        "/api/v1/sales/ferias/",
        {
            "customer_name": "Cliente Feria",
            "city_raw": "Medellín",
            "address_raw": "Cra 50 #10",
            "total_value": "89000",
            "qty_dorados": 2,
            "payment_account": "Efectivo",
        },
        format="json",
    )
    assert feria.status_code == 201
    assert feria.data["sale"]["source"] == "FERIAS"

    manual = api.post(
        "/api/v1/sales/manual/",
        {
            "customer_name": "Cliente Manual",
            "city_raw": "Cali",
            "address_raw": "Calle 5",
            "total_value": "50000",
            "qty_plateados": 1,
            "commercial_raw": "VENDEDORA 1",
            "payment_account": "Nequi",
        },
        format="json",
    )
    assert manual.status_code == 201
    assert manual.data["sale"]["source"] == "MANUAL"

    listed = api.get("/api/v1/sales/")
    assert listed.status_code == 200
    results = listed.data["results"] if "results" in listed.data else listed.data
    assert len(results) >= 2


@pytest.mark.django_db
def test_csv_import_dry_run_and_commit(api, admin_user):
    ensure_system_vendors()
    api.force_authenticate(user=admin_user)
    csv_text = (
        "external_id,source,customer_name,city_raw,total_value,qty_dorados,commercial_raw,status\n"
        "CSV-T1,FERIAS,Ana CSV,Bogotá,189000,1,FERIAS,completed\n"
        "CSV-T2,MANUAL,,Medellín,abc,1,VENDEDORA 1,completed\n"
    )
    dry = api.post(
        "/api/v1/sales/import/",
        {"csv": csv_text, "dry_run": True},
        format="json",
    )
    assert dry.status_code == 200
    assert dry.data["valid"] == 1
    assert dry.data["invalid"] == 1

    commit = api.post(
        "/api/v1/sales/import/",
        {"csv": csv_text, "dry_run": False, "on_duplicate": "skip"},
        format="json",
    )
    assert commit.status_code == 201
    assert commit.data["created"] == 1
    assert commit.data["rejected"] == 1
    assert ConsolidatedSale.objects.filter(external_id="CSV-T1").exists()
