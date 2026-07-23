import pytest
from rest_framework.test import APIClient

from apps.ai.models import DocumentKind
from apps.ai.services import ask_agent, ingest_document, similarity_search
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin-ai@test.seeds",
        password="testpass123",
        full_name="Admin AI",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
def test_ingest_and_search():
    ingest_document(
        kind=DocumentKind.POLICY,
        title="Política de devoluciones",
        content="Las devoluciones se aceptan dentro de 8 días hábiles con factura.",
    )
    hits = similarity_search("devoluciones factura días", limit=3)
    assert hits
    assert hits[0]["kind"] == DocumentKind.POLICY


@pytest.mark.django_db
def test_agent_sales_tool(admin_user):
    result = ask_agent("¿cuánto vendimos esta semana?", actor=admin_user)
    assert result["tool"] == "sales_summary"
    assert "answer" in result


@pytest.mark.django_db
def test_ai_api(api, admin_user):
    api.force_authenticate(user=admin_user)
    created = api.post(
        "/api/v1/ai/documents/",
        {
            "kind": "PRODUCT",
            "title": "Pack dorado",
            "content": "El pack dorado incluye tres unidades y es el más vendido en ferias.",
        },
        format="json",
    )
    assert created.status_code == 201

    search = api.get("/api/v1/ai/documents/search/", {"q": "pack dorado ferias"})
    assert search.status_code == 200
    assert search.data["results"]

    ask = api.post("/api/v1/ai/ask/", {"question": "ventas por vendedor este mes"}, format="json")
    assert ask.status_code == 200
    assert ask.data["tool"] == "sales_by_seller"
