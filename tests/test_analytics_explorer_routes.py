import pytest
from fastapi.testclient import TestClient

from analytics import explorer_routes as analytics_explorer_routes
from main import app


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def _fake_connection(monkeypatch):
    monkeypatch.setattr(analytics_explorer_routes, "get_connection", lambda: _FakeConn())


client = TestClient(app)


def _stat_row(symbol: str, **overrides) -> dict:
    row = {
        "coin_id": symbol.lower(),
        "symbol": symbol,
        "name": symbol.capitalize(),
        "image_url": None,
        "start_date": "2026-06-01",
        "end_date": "2026-06-30",
        "start_price": 100.0,
        "end_price": 110.0,
        "dollar_change": 10.0,
        "percent_change": 10.0,
        "low_price": 95.0,
        "high_price": 115.0,
        "avg_price": 105.0,
        "avg_volume": 1_000_000.0,
        "volatility_percent": 21.05,
        "start_rank": 10,
        "end_rank": 8,
        "rank_change": 2,
        "market_cap_usd": 50_000_000.0,
        "observation_count": 30,
    }
    row.update(overrides)
    return row


def _patch_stats(monkeypatch, rows):
    calls: list = []

    def _fetch(conn, from_date, to_date):
        calls.append((from_date, to_date))
        return rows

    monkeypatch.setattr(analytics_explorer_routes.repo, "fetch_period_stats", _fetch)
    return calls


def _query(**overrides) -> dict:
    body = {
        "metric": "price",
        "condition": "increased_by_percent",
        "from_date": "2026-06-01",
        "to_date": "2026-06-30",
        "threshold": 5.0,
    }
    body.update(overrides)
    return body


def test_query_returns_rows_summary_and_pagination_metadata(monkeypatch):
    calls = _patch_stats(
        monkeypatch,
        [
            _stat_row("BTC", percent_change=25.0),
            _stat_row("ETH", percent_change=7.5),
            _stat_row("SOL", percent_change=2.0),
        ],
    )

    response = client.post("/analytics/explorer/query", json=_query())

    assert response.status_code == 200
    body = response.json()
    assert [r["symbol"] for r in body["rows"]] == ["BTC", "ETH"]
    assert body["analysis_label"] == "Price increased by at least X%"
    assert body["total_results"] == 2
    assert body["sort_by"] == "percent_change"
    assert body["sort_order"] == "desc"
    assert body["summary"]["results_found"] == 2
    assert body["summary"]["largest_increase_symbol"] == "BTC"
    assert len(calls) == 1
    assert str(calls[0][0]) == "2026-06-01"
    assert str(calls[0][1]) == "2026-06-30"


def test_query_applies_offset_and_limit(monkeypatch):
    _patch_stats(monkeypatch, [_stat_row(f"C{i}", percent_change=float(i)) for i in range(1, 6)])

    response = client.post("/analytics/explorer/query", json=_query(threshold=0.0, limit=2, offset=2))

    assert response.status_code == 200
    body = response.json()
    assert [r["percent_change"] for r in body["rows"]] == [3.0, 2.0]
    assert body["total_results"] == 5


def test_query_rejects_inverted_date_range(monkeypatch):
    _patch_stats(monkeypatch, [])
    response = client.post(
        "/analytics/explorer/query", json=_query(from_date="2026-06-30", to_date="2026-06-01")
    )
    assert response.status_code == 400
    assert "from_date" in response.json()["detail"]


def test_query_rejects_unsupported_metric_condition_pair(monkeypatch):
    _patch_stats(monkeypatch, [])
    response = client.post(
        "/analytics/explorer/query", json=_query(metric="volume", condition="improved_by", threshold=1.0)
    )
    assert response.status_code == 400
    assert "No analysis is defined" in response.json()["detail"]


def test_query_rejects_missing_required_threshold(monkeypatch):
    _patch_stats(monkeypatch, [_stat_row("BTC")])
    response = client.post("/analytics/explorer/query", json=_query(threshold=None))
    assert response.status_code == 400
    assert "requires a threshold" in response.json()["detail"]


def test_query_validates_limit_bounds_as_422(monkeypatch):
    _patch_stats(monkeypatch, [])
    response = client.post("/analytics/explorer/query", json=_query(limit=0))
    assert response.status_code == 422


def test_export_returns_csv_attachment_with_all_qualifying_rows(monkeypatch):
    _patch_stats(
        monkeypatch,
        [
            _stat_row("BTC", percent_change=25.0),
            _stat_row("ETH", percent_change=7.5),
            _stat_row("SOL", percent_change=2.0),
        ],
    )

    # limit=1 must be ignored by the export: the CSV holds the full result set.
    response = client.post("/analytics/explorer/export", json=_query(limit=1))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="analytics-explorer_2026-06-01_2026-06-30.csv"' in response.headers["content-disposition"]
    lines = response.text.strip().split("\n")
    assert lines[0].startswith("Symbol,Coin,Start Date")
    assert len(lines) == 3  # header + BTC + ETH (SOL below threshold)
    assert lines[1].startswith("BTC,")
    assert lines[2].startswith("ETH,")


def test_export_propagates_validation_errors(monkeypatch):
    _patch_stats(monkeypatch, [])
    response = client.post(
        "/analytics/explorer/export", json=_query(from_date="2026-06-30", to_date="2026-06-01")
    )
    assert response.status_code == 400
