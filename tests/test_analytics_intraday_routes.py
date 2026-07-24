from datetime import datetime, timezone

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


def _row(**overrides) -> dict:
    row = {
        "coin_id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "observation_timestamp": datetime(2026, 7, 23, 9, 0, tzinfo=timezone.utc),
        "price_usd": 65000.0,
        "market_cap_usd": 1_300_000_000_000.0,
        "volume_24h_usd": 29_000_000_000.0,
    }
    row.update(overrides)
    return row


def test_get_intraday_returns_404_for_unknown_symbol(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_intraday", lambda conn, symbol: False)

    response = client.get("/analytics/intraday/zzz")

    assert response.status_code == 404


def test_get_intraday_returns_empty_list_when_tracked_but_no_observations(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_intraday", lambda conn, symbol: True)
    monkeypatch.setattr(
        analytics_routes.repo, "fetch_intraday", lambda conn, symbol, from_ts, to_ts, order, limit: []
    )

    response = client.get("/analytics/intraday/btc")

    assert response.status_code == 200
    assert response.json() == []


def test_get_intraday_rejects_from_after_to(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_intraday", lambda conn, symbol: True)

    response = client.get(
        "/analytics/intraday/btc",
        params={"from_timestamp": "2026-07-23T12:00:00Z", "to_timestamp": "2026-07-23T09:00:00Z"},
    )

    assert response.status_code == 400


def test_get_intraday_orders_chronologically_by_default(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_intraday", lambda conn, symbol: True)
    captured = {}

    def _fake_fetch(conn, symbol, from_ts, to_ts, order, limit):
        captured["order"] = order
        return [_row(), _row(observation_timestamp=datetime(2026, 7, 23, 9, 5, tzinfo=timezone.utc))]

    monkeypatch.setattr(analytics_routes.repo, "fetch_intraday", _fake_fetch)

    response = client.get("/analytics/intraday/btc")

    assert response.status_code == 200
    assert captured["order"] == "asc"
    assert len(response.json()) == 2


def test_get_intraday_passes_limit_and_order_through(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_intraday", lambda conn, symbol: True)
    captured = {}

    def _fake_fetch(conn, symbol, from_ts, to_ts, order, limit):
        captured["order"] = order
        captured["limit"] = limit
        return [_row()]

    monkeypatch.setattr(analytics_routes.repo, "fetch_intraday", _fake_fetch)

    response = client.get("/analytics/intraday/btc", params={"order": "desc", "limit": 10})

    assert response.status_code == 200
    assert captured["order"] == "desc"
    assert captured["limit"] == 10


def test_get_intraday_today_returns_404_for_unknown_symbol(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_intraday", lambda conn, symbol: False)

    response = client.get("/analytics/intraday/zzz/today")

    assert response.status_code == 404


def test_get_intraday_today_empty_list_when_no_observations_yet(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_intraday", lambda conn, symbol: True)
    monkeypatch.setattr(analytics_routes.repo, "fetch_intraday_today", lambda conn, symbol: [])

    response = client.get("/analytics/intraday/btc/today")

    assert response.status_code == 200
    assert response.json() == []


def test_get_intraday_today_success(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_intraday", lambda conn, symbol: True)
    monkeypatch.setattr(
        analytics_routes.repo,
        "fetch_intraday_today",
        lambda conn, symbol: [_row(), _row(observation_timestamp=datetime(2026, 7, 23, 9, 5, tzinfo=timezone.utc))],
    )

    response = client.get("/analytics/intraday/btc/today")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["symbol"] == "btc"


def test_daily_history_endpoint_unaffected_by_intraday_addition(monkeypatch):
    """Regression guard: adding the intraday routes must not touch /history/{symbol} behavior."""
    monkeypatch.setattr(analytics_routes.repo, "symbol_has_history", lambda conn, symbol: True)
    monkeypatch.setattr(
        analytics_routes.repo, "fetch_history", lambda conn, symbol, from_date, to_date, order, limit: []
    )

    response = client.get("/analytics/history/btc")

    assert response.status_code == 200
    assert response.json() == []
