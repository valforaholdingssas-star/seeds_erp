import hashlib
import hmac

import pytest
from rest_framework.test import APIClient

from apps.config import settings_service as cfg
from apps.logistics.models import BatchJob, BatchJobType
from apps.sales.services.kommo_client import enrich_from_webhook_payload
from apps.sales.tasks import verify_woo_signature
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="ops-admin@test.seeds",
        password="testpass123",
        full_name="Ops Admin",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
def test_woo_resync_empty_without_creds(api, admin_user):
    api.force_authenticate(user=admin_user)
    res = api.post(
        "/api/v1/sales/ecommerce/resync/",
        {"after": "2026-01-01", "before": "2026-01-31"},
        format="json",
    )
    assert res.status_code == 201
    assert res.data["total"] == 0
    assert res.data["job_type"] == BatchJobType.WOO_RESYNC
    assert BatchJob.objects.filter(job_type=BatchJobType.WOO_RESYNC).exists()


@pytest.mark.django_db
def test_kommo_enrich_from_enriched_payload():
    lead, contact = enrich_from_webhook_payload(
        {
            "lead": {"id": 99, "name": "Deal", "price": 100, "custom_fields_values": []},
            "contact": {"name": "Ana", "custom_fields_values": []},
        }
    )
    assert lead["id"] == 99
    assert contact["name"] == "Ana"


@pytest.mark.django_db
def test_config_test_envia_mock(api, admin_user):
    api.force_authenticate(user=admin_user)
    res = api.post("/api/v1/config/ENVIA/test/")
    assert res.status_code == 200
    assert res.data["ok"] is True
    assert res.data.get("mode") == "mock"


@pytest.mark.django_db
def test_verify_woo_signature_rejects_empty_secret(monkeypatch):
    monkeypatch.setattr(cfg, "get_secret", lambda key: "" if "webhook" in key else None)
    monkeypatch.setattr(cfg, "get_bool", lambda key, default=False: True)
    assert verify_woo_signature(b"{}", "") is False


@pytest.mark.django_db
def test_verify_woo_signature_allows_unsigned_when_disabled(monkeypatch):
    monkeypatch.setattr(cfg, "get_secret", lambda key: "" if "webhook" in key else None)
    monkeypatch.setattr(
        cfg,
        "get_bool",
        lambda key, default=False: False
        if key == "woocommerce.require_signature"
        else default,
    )
    assert verify_woo_signature(b"{}", "") is True


@pytest.mark.django_db
def test_verify_woo_signature_hmac(monkeypatch):
    secret = "test-woo-secret"
    body = b'{"id":1}'
    monkeypatch.setattr(cfg, "get_secret", lambda key: secret if "webhook" in key else None)
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_woo_signature(body, digest) is True
    assert verify_woo_signature(body, "bad") is False
