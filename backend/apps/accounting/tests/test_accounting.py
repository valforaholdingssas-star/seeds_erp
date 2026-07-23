import pytest
from rest_framework.test import APIClient

from apps.accounting.models import Invoice, InvoiceStatus, Refund
from apps.accounting.services.invoicing import (
    create_refund,
    ensure_invoice_for_sale,
    issue_invoice,
    reconcile_invoice,
)
from apps.sales.models import ConsolidatedSale, SaleSource, SaleState
from apps.sellers.services import ensure_system_vendors
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="acc-admin@test.seeds",
        password="testpass123",
        full_name="Acc Admin",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def sale(db):
    ensure_system_vendors()
    from apps.sellers.models import Vendedor

    return ConsolidatedSale.objects.create(
        source=SaleSource.MANUAL,
        external_id="ACC-100",
        seller=Vendedor.objects.get(name="ECOMMERCE"),
        customer_name="Cliente Fiscal",
        id_number="1234567890",
        email="fiscal@ex.com",
        city_raw="Bogotá",
        address_raw="Cll 1",
        total_value="119000",
        iva_generated="19000",
        net_value="100000",
        status="processing",
        state=SaleState.ACTIVE,
        income_source="MANUAL",
        requires_shipping=False,
    )


@pytest.mark.django_db
def test_issue_invoice_idempotent_mock(sale, admin_user):
    invoice = ensure_invoice_for_sale(sale)
    assert invoice.status == InvoiceStatus.POR_GENERAR

    issued = issue_invoice(invoice.id, actor=admin_user)
    assert issued.status == InvoiceStatus.GENERADA
    assert issued.number
    assert issued.alegra_id

    # second call must not re-emit
    again = issue_invoice(invoice.id, actor=admin_user)
    assert again.alegra_id == issued.alegra_id
    assert Invoice.objects.filter(sale=sale).count() == 1


@pytest.mark.django_db
def test_refund_generated_invoice(sale, admin_user):
    invoice = ensure_invoice_for_sale(sale)
    issue_invoice(invoice.id, actor=admin_user)
    refund = create_refund(invoice.id, reason="Cliente desistió", actor=admin_user)
    assert refund.alegra_credit_note_id
    invoice.refresh_from_db()
    sale.refresh_from_db()
    assert invoice.status == InvoiceStatus.ANULADA
    assert sale.state == SaleState.REFUNDED


@pytest.mark.django_db
def test_invoice_api_issue(api, admin_user, sale):
    ensure_invoice_for_sale(sale)
    api.force_authenticate(user=admin_user)
    inv = Invoice.objects.get(sale=sale)
    res = api.post(f"/api/v1/accounting/invoices/{inv.id}/issue/")
    assert res.status_code == 200
    assert res.data["status"] == "GENERADA"

    # ENVIANDO guard: force status and expect 400 on issue
    inv.status = InvoiceStatus.ENVIANDO
    inv.alegra_id = ""
    inv.number = ""
    inv.save()
    blocked = api.post(f"/api/v1/accounting/invoices/{inv.id}/issue/")
    assert blocked.status_code == 400

    reconciled = api.post(f"/api/v1/accounting/invoices/{inv.id}/reconcile/")
    assert reconciled.status_code == 200
    assert reconciled.data["status"] in {"POR_GENERAR", "GENERADA"}
