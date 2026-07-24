from datetime import date

import pytest
from fastapi.testclient import TestClient

from analytics import routes as analytics_routes
from main import app


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def _fake_connection(monkeypatch):
    monkeypatch.setattr(analytics_routes, "get_connection", lambda: _FakeConn())


client = TestClient(app)


def _summary_row(**overrides) -> dict:
    row = {
        "coin_id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "period_start_date": date(2026, 6, 23),
        "period_end_date": date(2026, 7, 23),
        "period_start_price": 50000.0,
        "period_end_price": 65000.0,
        "absolute_change": 15000.0,
        "percent_change": 30.0,
        "min_price": 48000.0,
        "max_price": 66000.0,
        "avg_price": 57000.0,
        "observation_count": 30,
    }
    row.update(overrides)
    return row


def test_get_history_summary_returns_404_for_unknown_symbol(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_history", lambda conn, symbol: False)

    response = client.get("/analytics/history/zzz/summary")

    assert response.status_code == 404


def test_get_history_summary_returns_404_when_no_rows_in_range(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_history", lambda conn, symbol: True)
    monkeypatch.setattr(
        analytics_routes.repo, "fetch_history_summary", lambda conn, symbol, from_date, to_date: None
    )

    response = client.get("/analytics/history/btc/summary")

    assert response.status_code == 404


def test_get_history_summary_rejects_from_date_after_to_date(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_history", lambda conn, symbol: True)

    response = client.get(
        "/analytics/history/btc/summary",
        params={"from_date": "2026-02-01", "to_date": "2026-01-01"},
    )

    assert response.status_code == 400


def test_get_history_summary_success(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_history", lambda conn, symbol: True)
    monkeypatch.setattr(
        analytics_routes.repo, "fetch_history_summary", lambda conn, symbol, from_date, to_date: _summary_row()
    )

    response = client.get("/analytics/history/btc/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["observation_count"] == 30
    assert body["absolute_change"] == 15000.0
    assert body["percent_change"] == 30.0


def test_get_history_summary_passes_date_range_through(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_history", lambda conn, symbol: True)
    captured = {}

    def _fake_summary(conn, symbol, from_date, to_date):
        captured["from_date"] = from_date
        captured["to_date"] = to_date
        return _summary_row()

    monkeypatch.setattr(analytics_routes.repo, "fetch_history_summary", _fake_summary)

    response = client.get(
        "/analytics/history/btc/summary",
        params={"from_date": "2026-06-01", "to_date": "2026-07-01"},
    )

    assert response.status_code == 200
    assert captured["from_date"] == date(2026, 6, 1)
    assert captured["to_date"] == date(2026, 7, 1)
