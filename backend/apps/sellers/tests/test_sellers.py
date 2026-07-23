import pytest
from rest_framework.test import APIClient

from apps.sellers.models import Vendedor
from apps.sellers.services import resolve_vendedor
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin-sellers@test.seeds",
        password="testpass123",
        full_name="Admin Sellers",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
def test_resolve_by_alias_and_auto_create():
    Vendedor.objects.create(name="VENDEDORA 1", aliases=["Marina", "Maji"], active=True)
    match = resolve_vendedor("marina")
    assert match is not None
    assert match.name == "VENDEDORA 1"

    unknown = resolve_vendedor("Comercial Nuevo XYZ")
    assert unknown is not None
    assert unknown.needs_review is True
    assert unknown.name == "Comercial Nuevo XYZ"


@pytest.mark.django_db
def test_sellers_crud_admin(api, admin_user):
    api.force_authenticate(user=admin_user)
    res = api.post(
        "/api/v1/sellers/",
        {"name": "VENDEDORA 2", "aliases": ["Sofi"], "active": True},
        format="json",
    )
    assert res.status_code == 201
    vendor_id = res.data["id"]

    listed = api.get("/api/v1/sellers/")
    assert listed.status_code == 200
    results = listed.data["results"] if "results" in listed.data else listed.data
    assert any(v["name"] == "VENDEDORA 2" for v in results)

    resolved = api.get("/api/v1/sellers/resolve/", {"q": "Sofi"})
    assert resolved.status_code == 200
    assert resolved.data["match"]["id"] == vendor_id

    seed = api.post("/api/v1/sellers/seed_system/")
    assert seed.status_code == 200
    assert Vendedor.objects.filter(name="ECOMMERCE", is_system=True).exists()
    assert Vendedor.objects.filter(name="FERIAS", is_system=True).exists()

    ecommerce = Vendedor.objects.get(name="ECOMMERCE")
    delete = api.delete(f"/api/v1/sellers/{ecommerce.id}/")
    assert delete.status_code == 400
