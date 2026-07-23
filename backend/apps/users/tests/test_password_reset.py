import pytest
from rest_framework.test import APIClient

from apps.users.models import PasswordResetToken, Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="pwd-admin@test.seeds",
        password="oldpass123",
        full_name="Pwd Admin",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
def test_password_reset_flow(api, admin_user, settings):
    settings.DEBUG = True
    unknown = api.post(
        "/api/v1/auth/password-reset/",
        {"email": "nobody@test.seeds"},
        format="json",
    )
    assert unknown.status_code == 200
    assert "detail" in unknown.data
    assert "debug_token" not in unknown.data

    req = api.post(
        "/api/v1/auth/password-reset/",
        {"email": admin_user.email},
        format="json",
    )
    assert req.status_code == 200
    token = req.data.get("debug_token")
    assert token
    assert PasswordResetToken.objects.filter(token=token).exists()

    bad = api.post(
        "/api/v1/auth/password-reset/confirm/",
        {"token": "invalid-token", "password": "newpass123"},
        format="json",
    )
    assert bad.status_code == 400

    ok = api.post(
        "/api/v1/auth/password-reset/confirm/",
        {"token": token, "password": "newpass123"},
        format="json",
    )
    assert ok.status_code == 200

    admin_user.refresh_from_db()
    assert admin_user.check_password("newpass123")
    assert not admin_user.check_password("oldpass123")

    reuse = api.post(
        "/api/v1/auth/password-reset/confirm/",
        {"token": token, "password": "anotherpass1"},
        format="json",
    )
    assert reuse.status_code == 400

    login = api.post(
        "/api/v1/auth/login/",
        {"email": admin_user.email, "password": "newpass123"},
        format="json",
    )
    assert login.status_code == 200
