import pytest
from rest_framework.test import APIClient

from apps.leads.models import Lead, LeadStatus
from apps.leads.services import can_transition, transition_lead
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin-leads@test.seeds",
        password="testpass123",
        full_name="Admin Leads",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def ventas_user(db):
    return User.objects.create_user(
        email="ventas-leads@test.seeds",
        password="testpass123",
        full_name="Ventas Leads",
        role=Role.VENTAS,
    )


@pytest.mark.django_db
def test_lead_transitions():
    lead = Lead.objects.create(name="Ana Pérez", source="web", status=LeadStatus.NUEVO)
    assert can_transition(LeadStatus.NUEVO, LeadStatus.CONTACTADO)
    transition_lead(lead, status=LeadStatus.CONTACTADO)
    lead.refresh_from_db()
    assert lead.status == LeadStatus.CONTACTADO
    assert not can_transition(LeadStatus.CONVERTIDO, LeadStatus.NUEVO)


@pytest.mark.django_db
def test_leads_crud_and_board(api, admin_user):
    api.force_authenticate(user=admin_user)
    res = api.post(
        "/api/v1/leads/",
        {
            "name": "Camila Ríos",
            "email": "camila@example.com",
            "city": "Bogotá",
            "source": "feria",
            "status": "NUEVO",
        },
        format="json",
    )
    assert res.status_code == 201
    lead_id = res.data["id"]

    listed = api.get("/api/v1/leads/")
    assert listed.status_code == 200

    board = api.get("/api/v1/leads/board/")
    assert board.status_code == 200
    assert "NUEVO" in board.data["columns"]

    moved = api.post(f"/api/v1/leads/{lead_id}/transition/", {"status": "CONTACTADO"}, format="json")
    assert moved.status_code == 200
    assert moved.data["status"] == "CONTACTADO"

    bulk = api.post(
        "/api/v1/leads/bulk_status/",
        {"ids": [lead_id], "status": "CALIFICADO"},
        format="json",
    )
    assert bulk.status_code == 200
    assert bulk.data["updated"] == 1


@pytest.mark.django_db
def test_ventas_can_create(api, ventas_user):
    api.force_authenticate(user=ventas_user)
    res = api.post(
        "/api/v1/leads/",
        {"name": "Lead Ventas", "source": "referido"},
        format="json",
    )
    assert res.status_code == 201
