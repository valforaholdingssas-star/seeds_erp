import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.config import settings_service as cfg
from apps.config.crypto import decrypt_secret, encrypt_secret, mask_secret
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@test.seeds",
        password="testpass123",
        full_name="Admin Test",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
def test_health(api):
    res = api.get("/api/health/")
    assert res.status_code == 200
    assert res.data["status"] == "ok"


@pytest.mark.django_db
def test_login_and_me(api, admin_user):
    res = api.post(
        "/api/v1/auth/login/",
        {"email": "admin@test.seeds", "password": "testpass123"},
        format="json",
    )
    assert res.status_code == 200
    assert "access" in res.data
    token = res.data["access"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    me = api.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.data["email"] == "admin@test.seeds"
    assert me.data["role"] == "ADMIN"


@pytest.mark.django_db
def test_secret_roundtrip_and_mask(admin_user):
    blob = encrypt_secret("super-secret-token-4821")
    assert decrypt_secret(blob) == "super-secret-token-4821"
    assert mask_secret("super-secret-token-4821") == "••••4821"

    cfg.set_value("envia.token_sandbox", "super-secret-token-4821", actor=admin_user)
    described = cfg.describe("envia.token_sandbox")
    assert described["is_secret"] is True
    assert described["value"] is None
    assert described["masked"] == "••••4821"
    assert cfg.get_secret("envia.token_sandbox") == "super-secret-token-4821"


@pytest.mark.django_db
def test_config_api_masks_secrets(api, admin_user):
    api.force_authenticate(user=admin_user)
    cfg.set_value("alegra.token", "alegra-token-9f02", actor=admin_user)
    res = api.get("/api/v1/config/")
    assert res.status_code == 200
    secrets = [s for s in res.data["settings"] if s["key"] == "alegra.token"]
    assert secrets
    assert secrets[0]["value"] is None
    assert secrets[0]["masked"] == "••••9f02"
