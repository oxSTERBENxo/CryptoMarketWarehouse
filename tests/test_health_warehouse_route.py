from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from main import app
from health.models import HealthCheck, WarehouseHealthResponse


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _canned_response(**overrides) -> WarehouseHealthResponse:
    base = dict(
        generated_at=datetime.now(timezone.utc),
        environment="development",
        overall_status="healthy",
        database=HealthCheck(status="healthy", message="Connected."),
        latest_successful_run=None,
        latest_failed_run=None,
        last_daily_snapshot_date=None,
        last_hourly_snapshot_at=None,
        daily_fact_row_count=0,
        hourly_fact_row_count=0,
        current_coin_count=0,
        historical_coin_version_count=0,
        recent_failed_run_count=0,
        data_quality=HealthCheck(status="healthy", message=""),
        duplicate_check=HealthCheck(status="healthy", message=""),
        missing_date_coverage=HealthCheck(status="healthy", message=""),
        missing_dates=[],
        stale_coin_check=HealthCheck(status="healthy", message=""),
        stale_coins=[],
        scheduler=HealthCheck(status="healthy", message=""),
        scheduler_status={},
    )
    base.update(overrides)
    return WarehouseHealthResponse(**base)


def test_health_warehouse_returns_aggregated_response(monkeypatch):
    monkeypatch.setattr(main, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(main, "get_warehouse_health", lambda conn: _canned_response())

    with TestClient(app) as client:
        response = client.get("/health/warehouse")

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "healthy"
    assert body["database"]["status"] == "healthy"
    assert "scheduler_status" in body


def test_health_warehouse_returns_200_even_when_overall_status_is_error(monkeypatch):
    """A degraded warehouse is still a successful health *check* -- the payload's own
    overall_status carries the bad news, not an HTTP error status, so the frontend can render a
    clear Warning/Error card instead of falling through to a generic fetch-failure banner."""
    monkeypatch.setattr(main, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(
        main,
        "get_warehouse_health",
        lambda conn: _canned_response(
            overall_status="error",
            database=HealthCheck(status="error", message="Database connection failed: timeout"),
        ),
    )

    with TestClient(app) as client:
        response = client.get("/health/warehouse")

    assert response.status_code == 200
    assert response.json()["overall_status"] == "error"
