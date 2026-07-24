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


def _current_market_result(**overrides) -> dict:
    result = {
        "refreshed_at": "2026-07-24T10:42:00+00:00",
        "coin_count": 2,
        "total_market_cap_usd": 1_500_000_000.0,
        "total_volume_24h_usd": 200_000_000.0,
        "coins": [
            {
                "coin_id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "price_usd": 68_500.0,
                "market_cap_usd": 1_000_000_000.0,
                "volume_24h_usd": 150_000_000.0,
                "circulating_supply": 19_000_000.0,
                "market_cap_rank": 1,
            },
            {
                "coin_id": "ethereum",
                "symbol": "eth",
                "name": "Ethereum",
                "price_usd": 3_200.0,
                "market_cap_usd": 500_000_000.0,
                "volume_24h_usd": 50_000_000.0,
                "circulating_supply": 120_000_000.0,
                "market_cap_rank": 2,
            },
        ],
    }
    result.update(overrides)
    return result


def test_get_current_market_returns_404_when_nothing_ingested(monkeypatch):
    monkeypatch.setattr(analytics_routes.repo, "fetch_current_market", lambda conn, limit, order: None)

    response = client.get("/analytics/current-market")

    assert response.status_code == 404


def test_get_current_market_success(monkeypatch):
    monkeypatch.setattr(
        analytics_routes.repo, "fetch_current_market", lambda conn, limit, order: _current_market_result()
    )

    response = client.get("/analytics/current-market")

    assert response.status_code == 200
    body = response.json()
    assert body["coin_count"] == 2
    assert body["refreshed_at"].startswith("2026-07-24T10:42:00")
    assert body["coins"][0]["symbol"] == "btc"
    assert body["coins"][0]["price_usd"] == 68_500.0


def test_get_current_market_reflects_latest_staging_run_regardless_of_snapshots_inserted(monkeypatch):
    """Part 8's core requirement: this endpoint must report fresh values even when the same-day
    warehouse fact row already exists (snapshots_inserted == 0 on /admin/refresh-market-data).
    It reads analytics.current_market_live (backed by the latest staging run), not the
    daily-grain analytics.latest_snapshot, so nothing here depends on dw.fact_market_snapshot
    having changed at all."""
    calls: list[tuple] = []

    def _fetch(conn, limit, order):
        calls.append((limit, order))
        return _current_market_result(coins=[{**_current_market_result()["coins"][0], "price_usd": 69_000.0}])

    monkeypatch.setattr(analytics_routes.repo, "fetch_current_market", _fetch)

    response = client.get("/analytics/current-market")

    assert response.status_code == 200
    assert response.json()["coins"][0]["price_usd"] == 69_000.0
    assert calls == [(None, "desc")]


def test_get_current_market_rejects_out_of_range_limit_with_422(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("repository must not be called when validation fails")

    monkeypatch.setattr(analytics_routes.repo, "fetch_current_market", _fail)

    response = client.get("/analytics/current-market", params={"limit": 99999})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Part 16 (1-6): price_change_percentage_24h / image_url serialization
# ---------------------------------------------------------------------------


def _coin_with(**overrides) -> dict:
    coin = dict(_current_market_result()["coins"][0])
    coin.update(overrides)
    return coin


def test_current_market_serializes_positive_price_change(monkeypatch):
    monkeypatch.setattr(
        analytics_routes.repo,
        "fetch_current_market",
        lambda conn, limit, order: _current_market_result(coins=[_coin_with(price_change_percentage_24h=1.84)]),
    )

    response = client.get("/analytics/current-market")

    assert response.status_code == 200
    assert response.json()["coins"][0]["price_change_percentage_24h"] == 1.84


def test_current_market_serializes_negative_price_change(monkeypatch):
    monkeypatch.setattr(
        analytics_routes.repo,
        "fetch_current_market",
        lambda conn, limit, order: _current_market_result(coins=[_coin_with(price_change_percentage_24h=-2.31)]),
    )

    response = client.get("/analytics/current-market")

    assert response.status_code == 200
    assert response.json()["coins"][0]["price_change_percentage_24h"] == -2.31


def test_current_market_serializes_zero_price_change(monkeypatch):
    monkeypatch.setattr(
        analytics_routes.repo,
        "fetch_current_market",
        lambda conn, limit, order: _current_market_result(coins=[_coin_with(price_change_percentage_24h=0.0)]),
    )

    response = client.get("/analytics/current-market")

    assert response.status_code == 200
    assert response.json()["coins"][0]["price_change_percentage_24h"] == 0.0


def test_current_market_serializes_null_price_change(monkeypatch):
    monkeypatch.setattr(
        analytics_routes.repo,
        "fetch_current_market",
        lambda conn, limit, order: _current_market_result(coins=[_coin_with(price_change_percentage_24h=None)]),
    )

    response = client.get("/analytics/current-market")

    assert response.status_code == 200
    assert response.json()["coins"][0]["price_change_percentage_24h"] is None


def test_current_market_serializes_image_url_present(monkeypatch):
    monkeypatch.setattr(
        analytics_routes.repo,
        "fetch_current_market",
        lambda conn, limit, order: _current_market_result(
            coins=[_coin_with(image_url="https://assets.coingecko.com/coins/images/1/large/bitcoin.png")]
        ),
    )

    response = client.get("/analytics/current-market")

    assert response.status_code == 200
    assert response.json()["coins"][0]["image_url"] == "https://assets.coingecko.com/coins/images/1/large/bitcoin.png"


def test_current_market_serializes_image_url_null(monkeypatch):
    monkeypatch.setattr(
        analytics_routes.repo,
        "fetch_current_market",
        lambda conn, limit, order: _current_market_result(coins=[_coin_with(image_url=None)]),
    )

    response = client.get("/analytics/current-market")

    assert response.status_code == 200
    assert response.json()["coins"][0]["image_url"] is None
