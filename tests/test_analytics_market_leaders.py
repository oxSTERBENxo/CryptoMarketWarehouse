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


def _mover(symbol: str, **overrides) -> dict:
    row = {
        "coin_id": symbol.lower(),
        "symbol": symbol,
        "name": symbol.capitalize(),
        "start_price": 100.0,
        "end_price": 110.0,
        "percent_change": 10.0,
        "high_price": 115.0,
        "low_price": 95.0,
        "volatility_percent": 21.05,
        "volume_24h_usd": 1_000_000.0,
        "market_cap_usd": 50_000_000.0,
        "market_cap_rank": 5,
        "observation_count": 3,
    }
    row.update(overrides)
    return row


def _patch(
    monkeypatch,
    *,
    daily=None,
    intraday=None,
    coin_count=20,
    latest_update_at=None,
    daily_range=(None, None),
    intraday_range=(None, None),
):
    daily_calls: list = []
    intraday_calls: list = []

    def _daily(conn, from_date, to_date):
        daily_calls.append((from_date, to_date))
        return daily if daily is not None else []

    def _intraday(conn, from_ts, to_ts):
        intraday_calls.append((from_ts, to_ts))
        return intraday if intraday is not None else []

    monkeypatch.setattr(analytics_routes.repo, "fetch_daily_movers", _daily)
    monkeypatch.setattr(analytics_routes.repo, "fetch_intraday_movers", _intraday)
    monkeypatch.setattr(analytics_routes.repo, "fetch_coin_count", lambda conn: coin_count)
    monkeypatch.setattr(analytics_routes.repo, "fetch_latest_update_at", lambda conn: latest_update_at)
    monkeypatch.setattr(analytics_routes.repo, "fetch_daily_observation_range", lambda conn, f, t: daily_range)
    monkeypatch.setattr(analytics_routes.repo, "fetch_intraday_observation_range", lambda conn, f, t: intraday_range)
    return daily_calls, intraday_calls


def test_default_period_uses_daily_movers_and_ranks_by_percent_change(monkeypatch):
    rows = [
        _mover("BTC", percent_change=5.0),
        _mover("ETH", percent_change=-8.0),
        _mover("SOL", percent_change=20.0),
    ]
    _patch(monkeypatch, daily=rows, intraday=[])

    response = client.get("/analytics/market-leaders")

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "7d"
    assert [e["symbol"] for e in body["gainers"]] == ["SOL", "BTC", "ETH"]
    assert [e["symbol"] for e in body["losers"]] == ["ETH", "BTC", "SOL"]


def test_today_period_uses_intraday_movers_only_once(monkeypatch):
    rows = [_mover("BTC", percent_change=3.0)]
    daily_calls, intraday_calls = _patch(monkeypatch, daily=[], intraday=rows)

    response = client.get("/analytics/market-leaders", params={"period": "today"})

    assert response.status_code == 200
    assert len(daily_calls) == 0
    assert len(intraday_calls) == 1
    body = response.json()
    assert body["gainers"][0]["symbol"] == "BTC"
    assert body["summary"]["today_best_performer"]["symbol"] == "BTC"


def test_non_today_period_still_computes_summary_from_intraday(monkeypatch):
    daily_rows = [_mover("BTC", percent_change=5.0)]
    intraday_rows = [_mover("ETH", percent_change=-2.0), _mover("SOL", percent_change=4.0)]
    daily_calls, intraday_calls = _patch(monkeypatch, daily=daily_rows, intraday=intraday_rows)

    response = client.get("/analytics/market-leaders", params={"period": "30d"})

    assert response.status_code == 200
    assert len(daily_calls) == 1
    assert len(intraday_calls) == 1
    body = response.json()
    assert body["gainers"][0]["symbol"] == "BTC"
    assert body["summary"]["today_best_performer"]["symbol"] == "SOL"
    assert body["summary"]["today_worst_performer"]["symbol"] == "ETH"
    assert body["summary"]["average_market_movement_percent"] == pytest.approx(1.0)


def test_limit_truncates_gainers_and_losers(monkeypatch):
    rows = [_mover(f"C{i}", percent_change=float(i)) for i in range(10)]
    _patch(monkeypatch, daily=rows, intraday=[])

    response = client.get("/analytics/market-leaders", params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert len(body["gainers"]) == 2
    assert len(body["losers"]) == 2


def test_highlight_stats_ignore_null_fields(monkeypatch):
    rows = [
        _mover("BTC", volume_24h_usd=None, market_cap_rank=1, volatility_percent=None),
        _mover("ETH", volume_24h_usd=500.0, market_cap_rank=None, volatility_percent=15.0),
    ]
    _patch(monkeypatch, daily=rows, intraday=[])

    response = client.get("/analytics/market-leaders")

    assert response.status_code == 200
    body = response.json()
    assert body["highest_volume"]["symbol"] == "ETH"
    assert body["highest_ranked"]["symbol"] == "BTC"
    assert body["most_volatile"]["symbol"] == "ETH"


def test_empty_data_returns_empty_lists_and_null_highlights(monkeypatch):
    _patch(monkeypatch, daily=[], intraday=[])

    response = client.get("/analytics/market-leaders")

    assert response.status_code == 200
    body = response.json()
    assert body["gainers"] == []
    assert body["losers"] == []
    assert body["highest_volume"] is None
    assert body["highest_ranked"] is None
    assert body["most_volatile"] is None
    assert body["summary"]["today_best_performer"] is None
    assert body["summary"]["average_market_movement_percent"] is None


def test_summary_reports_total_tracked_coins_and_latest_update(monkeypatch):
    latest = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
    _patch(monkeypatch, daily=[], intraday=[], coin_count=42, latest_update_at=latest)

    response = client.get("/analytics/market-leaders")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_tracked_coins"] == 42
    assert body["summary"]["latest_update_at"] is not None


def test_rejects_invalid_period_with_422(monkeypatch):
    _patch(monkeypatch, daily=[], intraday=[])

    response = client.get("/analytics/market-leaders", params={"period": "sideways"})

    assert response.status_code == 422


def test_7d_leaderboard_is_not_empty_with_realistic_gapped_data(monkeypatch):
    """Regression test for the Market Leaders 7D bug: a realistic mix of coins -- one gainer, one
    loser, one flat, one with a gap between its first/last observation dates, and coins missing
    optional rank/volume -- must still produce a non-empty, correctly-ranked 7D leaderboard.
    fetch_daily_movers already resolves gaps at the SQL layer (first/last real observation in
    range); this asserts the route never re-excludes what the repository already qualified."""
    rows = [
        _mover("GAIN", start_price=100.0, end_price=120.0, percent_change=20.0, observation_count=2),
        _mover("LOSE", start_price=100.0, end_price=80.0, percent_change=-20.0, observation_count=2),
        _mover("FLAT", start_price=100.0, end_price=100.0, percent_change=0.0, observation_count=2),
        # First/last observation five days apart (a gap in between) -- still just 2 real rows.
        _mover("GAPPY", start_price=50.0, end_price=55.0, percent_change=10.0, observation_count=2),
        # Optional fields missing must not exclude the coin from gainers/losers.
        _mover("NORANK", start_price=10.0, end_price=11.0, percent_change=10.0, market_cap_rank=None),
        _mover("NOVOL", start_price=10.0, end_price=9.0, percent_change=-10.0, volume_24h_usd=None),
    ]
    _patch(
        monkeypatch,
        daily=rows,
        intraday=[],
        daily_range=(datetime(2026, 7, 16), datetime(2026, 7, 23)),
    )

    response = client.get("/analytics/market-leaders", params={"period": "7d", "limit": 10})

    assert response.status_code == 200
    body = response.json()

    assert body["gainers"] != []
    assert body["losers"] != []

    gainer_symbols = [e["symbol"] for e in body["gainers"]]
    loser_symbols = [e["symbol"] for e in body["losers"]]
    assert "GAIN" in gainer_symbols
    assert "LOSE" in loser_symbols
    assert "GAPPY" in gainer_symbols  # the gap between its two observations must not exclude it
    assert "NORANK" in gainer_symbols  # missing market_cap_rank must not exclude it
    assert "NOVOL" in loser_symbols  # missing volume_24h_usd must not exclude it

    gain_entry = next(e for e in body["gainers"] if e["symbol"] == "GAIN")
    assert gain_entry["percent_change"] == pytest.approx(20.0)
    lose_entry = next(e for e in body["losers"] if e["symbol"] == "LOSE")
    assert lose_entry["percent_change"] == pytest.approx(-20.0)

    assert body["coverage"]["qualifying_coin_count"] == len(rows)
    assert body["coverage"]["empty_reason"] is None
    assert body["coverage"]["earliest_observation"] is not None
    assert body["coverage"]["latest_observation"] is not None


def test_coverage_distinguishes_no_history_from_nothing_qualified(monkeypatch):
    _patch(monkeypatch, daily=[], intraday=[], daily_range=(None, None))

    response = client.get("/analytics/market-leaders", params={"period": "7d"})

    body = response.json()
    assert body["coverage"]["qualifying_coin_count"] == 0
    assert body["coverage"]["empty_reason"] == "Daily history has not been loaded for this period."


def test_coverage_reports_nothing_qualified_when_history_exists_but_all_single_observation(monkeypatch):
    # History was loaded for the range (observation dates exist) but fetch_daily_movers excluded
    # every coin because none had >=2 observations in range.
    _patch(
        monkeypatch,
        daily=[],
        intraday=[],
        daily_range=(datetime(2026, 7, 16), datetime(2026, 7, 23)),
    )

    response = client.get("/analytics/market-leaders", params={"period": "7d"})

    body = response.json()
    assert body["coverage"]["qualifying_coin_count"] == 0
    assert body["coverage"]["empty_reason"] == "No coins have at least two valid observations in this range."


def test_today_coverage_uses_intraday_specific_empty_reason(monkeypatch):
    _patch(monkeypatch, daily=[], intraday=[], intraday_range=(None, None))

    response = client.get("/analytics/market-leaders", params={"period": "today"})

    body = response.json()
    assert body["coverage"]["empty_reason"] == "No intraday observations loaded yet today."
