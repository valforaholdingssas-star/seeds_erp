import pytest
from rest_framework.test import APIClient

from apps.sales.models import ConsolidatedSale, PaymentMethod, SaleSource, SaleState
from apps.sales.services.payment_methods import (
    apply_payment_method_name,
    ensure_default_payment_methods,
    resolve_payment_method,
)
from apps.sellers.services import ensure_system_vendors
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="pay-admin@test.seeds",
        password="testpass123",
        full_name="Pay Admin",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
def test_resolve_and_rename_propagates(admin_user):
    ensure_default_payment_methods()
    ensure_system_vendors()
    nequi = resolve_payment_method("nequi")
    assert nequi is not None
    assert nequi.name == "Nequi"

    from apps.sellers.models import Vendedor

    seller = Vendedor.objects.get(name="ECOMMERCE")
    sale = ConsolidatedSale.objects.create(
        source=SaleSource.MANUAL,
        external_id="PAY-1",
        seller=seller,
        customer_name="Ana",
        total_value="100000",
        payment_account=nequi.name,
        payment_method=nequi,
        status="completed",
        state=SaleState.ACTIVE,
    )

    nequi.name = "Nequi Seeds"
    nequi.save()
    apply_payment_method_name(nequi)
    sale.refresh_from_db()
    assert sale.payment_account == "Nequi Seeds"
    assert sale.payment_method_id == nequi.id


@pytest.mark.django_db
def test_payment_methods_api_and_form_dropdown(api, admin_user):
    api.force_authenticate(user=admin_user)
    listed = api.get("/api/v1/payment-methods/?active_only=1")
    assert listed.status_code == 200
    results = listed.data["results"] if "results" in listed.data else listed.data
    assert len(results) >= 1

    created = api.post(
        "/api/v1/payment-methods/",
        {"name": "Daviplata", "aliases": ["davi"], "active": True},
        format="json",
    )
    assert created.status_code == 201
    pm_id = created.data["id"]

    renamed = api.patch(
        f"/api/v1/payment-methods/{pm_id}/",
        {"name": "Daviplata Seeds"},
        format="json",
    )
    assert renamed.status_code == 200
    assert renamed.data["name"] == "Daviplata Seeds"
