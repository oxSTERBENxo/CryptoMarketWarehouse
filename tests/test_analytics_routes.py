from datetime import date

import pytest
from fastapi.testclient import TestClient

from analytics import routes as analytics_routes
from main import app


class _FakeConn:
    """Minimal stand-in for a psycopg3 Connection's context-manager protocol, so tests can
    exercise the real `analytics_routes._get_db` generator (including FastAPI's exception-into-
    generator cleanup behavior on request-validation failures) without a live database."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def _fake_connection(monkeypatch):
    monkeypatch.setattr(analytics_routes, "get_connection", lambda: _FakeConn())


client = TestClient(app)


def _overview_row(**overrides) -> dict:
    row = {
        "snapshot_date": date(2026, 7, 23),
        "coin_count": 20,
        "total_market_cap_usd": 1_000_000.0,
        "total_volume_24h_usd": 50_000.0,
    }
    row.update(overrides)
    return row


def test_get_overview_returns_404_when_no_snapshot(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "fetch_overview", lambda conn: None)

    response = client.get("/analytics/overview")

    assert response.status_code == 404


def test_get_overview_success(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "fetch_overview", lambda conn: _overview_row())

    response = client.get("/analytics/overview")

    assert response.status_code == 200
    assert response.json()["coin_count"] == 20


def test_get_latest_rejects_out_of_range_limit_with_422_not_503(monkeypatch):
    """Regression test: a query-param validation failure (limit > 500) must surface as 422,
    not be misreported as 503 by the DB dependency (see analytics_routes._get_db). Exercises
    the real dependency generator via _fake_connection rather than overriding it, since
    dependency_overrides would bypass the exact code path the bug lived in."""

    def _fail(*args, **kwargs):
        raise AssertionError("repository must not be called when validation fails")

    monkeypatch.setattr(analytics_routes.repo, "fetch_latest", _fail)

    response = client.get("/analytics/latest", params={"limit": 99999})

    assert response.status_code == 422


def test_get_latest_rejects_invalid_order_with_422_not_503(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("repository must not be called when validation fails")

    monkeypatch.setattr(analytics_routes.repo, "fetch_latest", _fail)

    response = client.get("/analytics/latest", params={"order": "sideways"})

    assert response.status_code == 422


def test_get_latest_success(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "fetch_latest", lambda conn, limit, order: [])

    response = client.get("/analytics/latest", params={"limit": 5})

    assert response.status_code == 200
    assert response.json() == []


def test_get_history_returns_404_for_unknown_symbol(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_history", lambda conn, symbol: False)

    response = client.get("/analytics/history/zzz")

    assert response.status_code == 404


def test_get_history_rejects_from_date_after_to_date(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_history", lambda conn, symbol: True)

    response = client.get(
        "/analytics/history/btc",
        params={"from_date": "2026-02-01", "to_date": "2026-01-01"},
    )

    assert response.status_code == 400
