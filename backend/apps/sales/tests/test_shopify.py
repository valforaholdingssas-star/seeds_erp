import base64
import hashlib
import hmac
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.config import settings_service as cfg
from apps.logistics.models import BatchJob, BatchJobType
from apps.sales.models import ConsolidatedSale, SaleSource, SaleState, ShopifySale
from apps.sales.services.shopify import map_shopify_status, upsert_shopify_from_payload
from apps.sales.tasks import verify_shopify_signature
from apps.sellers.services import ensure_system_vendors
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="shopify-admin@test.seeds",
        password="testpass123",
        full_name="Shopify Admin",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


def _shopify_order(**overrides):
    base = {
        "id": 5678901234,
        "name": "#1001",
        "email": "cliente@example.com",
        "created_at": "2026-07-01T12:00:00-05:00",
        "financial_status": "paid",
        "fulfillment_status": None,
        "cancelled_at": None,
        "cancel_reason": None,
        "total_price": "119000.00",
        "subtotal_price": "109000.00",
        "note": "",
        "note_attributes": [{"name": "cedula", "value": "1020304050"}],
        "payment_gateway_names": ["Mercado Pago"],
        "shipping_lines": [{"price": "10000.00"}],
        "shipping_address": {
            "first_name": "Ana",
            "last_name": "Pérez",
            "address1": "Cll 10 #20-30",
            "address2": "",
            "city": "Bogotá",
            "province": "Cundinamarca",
            "phone": "3001234567",
        },
        "line_items": [
            {
                "id": 1,
                "product_id": 111,
                "variant_id": 222,
                "name": "Kit Seeds - Dorado",
                "title": "Kit Seeds",
                "variant_title": "Dorado",
                "quantity": 1,
                "properties": [],
            },
            {
                "id": 2,
                "product_id": 112,
                "variant_id": 223,
                "name": "Kit Seeds - Plateado",
                "title": "Kit Seeds",
                "variant_title": "Plateado",
                "quantity": 2,
                "properties": [],
            },
        ],
    }
    base.update(overrides)
    return base


@pytest.mark.django_db
def test_map_shopify_status():
    assert map_shopify_status({"financial_status": "paid"}) == "processing"
    assert (
        map_shopify_status({"financial_status": "paid", "fulfillment_status": "fulfilled"})
        == "completed"
    )
    assert map_shopify_status({"financial_status": "pending"}) == "pending"
    assert map_shopify_status({"financial_status": "authorized"}) == "pending"
    assert map_shopify_status({"financial_status": "partially_paid"}) == "pending"
    assert map_shopify_status({"financial_status": "partially_refunded"}) == "processing"
    assert map_shopify_status({"cancelled_at": "2026-01-01", "financial_status": "paid"}) == "cancelled"
    assert map_shopify_status({"financial_status": "refunded"}) == "refunded"


@pytest.mark.django_db
def test_upsert_shopify_partially_paid_does_not_consolidate(admin_user):
    ensure_system_vendors()
    upsert_shopify_from_payload(
        _shopify_order(financial_status="partially_paid"),
        actor=admin_user,
    )
    assert ShopifySale.objects.filter(external_id="5678901234", status="pending").exists()
    assert not ConsolidatedSale.objects.filter(
        source=SaleSource.SHOPIFY, external_id="5678901234"
    ).exists()


@pytest.mark.django_db
def test_upsert_shopify_promotes_paid(admin_user):
    ensure_system_vendors()
    sale = upsert_shopify_from_payload(_shopify_order(), actor=admin_user)
    assert isinstance(sale, ConsolidatedSale) or isinstance(sale, ShopifySale)
    src = ShopifySale.objects.get(external_id="5678901234")
    assert src.status == "processing"
    assert src.id_number == "1020304050"
    assert src.qty_dorados == 1
    assert src.qty_plateados == 2
    cons = ConsolidatedSale.objects.get(source=SaleSource.SHOPIFY, external_id="5678901234")
    assert cons.state == SaleState.ACTIVE
    assert cons.total_value == Decimal("119000.00")
    assert cons.amount_shipping == Decimal("10000.00")
    assert cons.customer_name == "Ana Pérez"


@pytest.mark.django_db
def test_upsert_shopify_pending_does_not_consolidate(admin_user):
    ensure_system_vendors()
    upsert_shopify_from_payload(
        _shopify_order(financial_status="pending"),
        actor=admin_user,
    )
    assert ShopifySale.objects.filter(external_id="5678901234").exists()
    assert not ConsolidatedSale.objects.filter(
        source=SaleSource.SHOPIFY, external_id="5678901234"
    ).exists()


@pytest.mark.django_db
def test_upsert_shopify_cancelled_withdraws(admin_user):
    ensure_system_vendors()
    upsert_shopify_from_payload(_shopify_order(), actor=admin_user)
    upsert_shopify_from_payload(
        _shopify_order(cancelled_at="2026-07-02T10:00:00-05:00", cancel_reason="customer"),
        actor=admin_user,
    )
    cons = ConsolidatedSale.objects.get(source=SaleSource.SHOPIFY, external_id="5678901234")
    assert cons.state == SaleState.WITHDRAWN


@pytest.mark.django_db
def test_verify_shopify_signature_hmac(monkeypatch):
    secret = "shpss_test_secret"
    body = b'{"id":1}'
    monkeypatch.setattr(cfg, "get_secret", lambda key: secret if "api_secret" in key else None)
    monkeypatch.setattr(cfg, "get_bool", lambda key, default=False: True)
    digest = base64.b64encode(
        hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")
    assert verify_shopify_signature(body, digest) is True
    assert verify_shopify_signature(body, "bad") is False


@pytest.mark.django_db
def test_shopify_webhook_accepts_signed(api, admin_user, monkeypatch):
    secret = "shpss_test_secret"
    body = b'{"id":999,"financial_status":"paid","line_items":[],"total_price":"0"}'
    digest = base64.b64encode(
        hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")
    monkeypatch.setattr(cfg, "get_secret", lambda key: secret if "api_secret" in key else "")
    monkeypatch.setattr(
        "apps.sales.views.process_raw_event.delay",
        lambda *_a, **_k: None,
    )
    res = api.generic(
        "POST",
        "/api/v1/webhooks/shopify/orders/",
        data=body,
        content_type="application/json",
        HTTP_X_SHOPIFY_HMAC_SHA256=digest,
        HTTP_X_SHOPIFY_TOPIC="orders/create",
        HTTP_X_SHOPIFY_WEBHOOK_ID="wh-1",
    )
    assert res.status_code == 200
    assert res.data["status"] == "accepted"


@pytest.mark.django_db
def test_shopify_resync_empty_without_creds(api, admin_user):
    api.force_authenticate(user=admin_user)
    res = api.post(
        "/api/v1/sales/shopify/resync/",
        {"after": "2026-01-01", "before": "2026-01-31"},
        format="json",
    )
    assert res.status_code == 201
    assert res.data["total"] == 0
    assert res.data["job_type"] == BatchJobType.SHOPIFY_RESYNC
    assert BatchJob.objects.filter(job_type=BatchJobType.SHOPIFY_RESYNC).exists()
