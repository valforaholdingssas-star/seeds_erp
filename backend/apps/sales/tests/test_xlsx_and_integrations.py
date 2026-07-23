import io

import pytest
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.integrations.models import IntegrationSource, RawEventStatus, RawWebhookEvent
from apps.sales.models import ConsolidatedSale
from apps.sales.services.csv_import import xlsx_to_csv_text
from apps.sellers.models import Vendedor
from apps.sellers.services import ensure_system_vendors
from apps.users.models import Role, User


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="xlsx-admin@test.seeds",
        password="testpass123",
        full_name="XLSX Admin",
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


def _xlsx_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.django_db
def test_xlsx_import_api(api, admin_user):
    ensure_system_vendors()
    api.force_authenticate(user=admin_user)
    data = _xlsx_bytes(
        [
            [
                "external_id",
                "source",
                "customer_name",
                "city_raw",
                "total_value",
                "qty_dorados",
                "commercial_raw",
                "status",
            ],
            ["XLSX-1", "FERIAS", "Ana XLSX", "Bogotá", 189000, 1, "FERIAS", "completed"],
        ]
    )
    assert "Ana XLSX" in xlsx_to_csv_text(data)

    upload = io.BytesIO(data)
    upload.name = "ventas.xlsx"
    res = api.post(
        "/api/v1/sales/import/",
        {"file": upload, "dry_run": "false", "on_duplicate": "skip"},
        format="multipart",
    )
    assert res.status_code == 201
    assert res.data["created"] == 1
    assert ConsolidatedSale.objects.filter(external_id="XLSX-1").exists()


@pytest.mark.django_db
def test_vendedor_monthly_goal_in_summary(api, admin_user):
    ensure_system_vendors()
    vendor = Vendedor.objects.create(
        name="GOAL SELLER",
        monthly_goal="1000000",
        active=True,
    )
    api.force_authenticate(user=admin_user)
    listed = api.get(f"/api/v1/sellers/{vendor.id}/")
    assert listed.status_code == 200
    assert listed.data["monthly_goal"] == "1000000.00"

    summary = api.get(f"/api/v1/analytics/sales/summary/?seller={vendor.id}")
    assert summary.status_code == 200
    # Full-month prorate from day 1 → goal reflected in goal_month
    assert summary.data["kpis"]["goal_month"] == "1000000.00"


@pytest.mark.django_db
def test_integration_events_list_failed_and_reprocess(api, admin_user):
    api.force_authenticate(user=admin_user)
    event = RawWebhookEvent.objects.create(
        source=IntegrationSource.WOOCOMMERCE,
        event_type="order-updated",
        payload={"id": 1, "status": "pending"},
        status=RawEventStatus.FAILED,
        error="boom",
        dedupe_key="test:woo:1",
        attempts=1,
    )
    listed = api.get("/api/v1/integrations/events/?status=FAILED")
    assert listed.status_code == 200
    results = listed.data["results"] if "results" in listed.data else listed.data
    assert any(str(r["id"]) == str(event.id) for r in results)

    reprocessed = api.post(f"/api/v1/integrations/events/{event.id}/reprocess/")
    assert reprocessed.status_code == 202
    event.refresh_from_db()
    # Eager celery: pending payload without valid consolidatable status → PROCESSED or FAILED
    assert event.status in {
        RawEventStatus.PROCESSED,
        RawEventStatus.FAILED,
        RawEventStatus.IGNORED,
        RawEventStatus.RECEIVED,
    }
    assert event.attempts >= 2
