from datetime import datetime, timezone

import pytest

from etl import ingest_intraday_market_data as ingest
from integrations.coingecko import CoinGeckoAPIError, CoinIntradayObservation


class _FakeCursor:
    def __init__(self, run_id: int = 1, coin_key: int | None = 42):
        self.run_id = run_id
        self.coin_key = coin_key
        self.executed: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        if "coin_key" in self.executed[-1][0] and "dim_coin" in self.executed[-1][0]:
            return (self.coin_key,) if self.coin_key is not None else None
        return (self.run_id,)


class _FakeConn:
    def __init__(self, coin_key: int | None = 42):
        self.coin_key = coin_key
        self.committed = 0

    def cursor(self, **kwargs):
        return _FakeCursor(coin_key=self.coin_key)

    def commit(self):
        self.committed += 1


def _obs(price: float = 100.0, minute: int = 0) -> CoinIntradayObservation:
    return CoinIntradayObservation(
        observation_timestamp=datetime(2026, 7, 23, 12, minute, tzinfo=timezone.utc),
        price_usd=price,
        market_cap_usd=1_000_000.0,
        volume_24h_usd=500_000.0,
    )


def test_get_current_coin_key_returns_none_for_untracked_coin():
    cur = _FakeCursor(coin_key=None)
    assert ingest.get_current_coin_key(cur, "unknown-coin") is None


def test_run_intraday_ingest_skips_untracked_coin(monkeypatch):
    conn = _FakeConn(coin_key=None)
    monkeypatch.setattr(ingest.time, "sleep", lambda seconds: None)

    summary = ingest.run_intraday_ingest(conn, ["ghost-coin"], retention_days=None)

    assert summary.coins_failed == ["ghost-coin"]
    assert summary.observations_loaded == 0


def test_run_intraday_ingest_loads_observations(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setattr(ingest, "fetch_with_retry", lambda coin_id, days, max_retries: [_obs(), _obs(minute=5)])
    monkeypatch.setattr(ingest, "load_observations", lambda conn, coin_key, observations: (len(observations), 0))
    monkeypatch.setattr(ingest.time, "sleep", lambda seconds: None)

    summary = ingest.run_intraday_ingest(conn, ["bitcoin"], retention_days=None)

    assert summary.observations_loaded == 2
    assert summary.observations_skipped == 0
    assert summary.coins_failed == []


def test_run_intraday_ingest_continues_past_coin_failure(monkeypatch):
    conn = _FakeConn()

    def _fetch(coin_id, days, max_retries):
        if coin_id == "bitcoin":
            raise CoinGeckoAPIError("boom")
        return [_obs()]

    monkeypatch.setattr(ingest, "fetch_with_retry", _fetch)
    monkeypatch.setattr(ingest, "load_observations", lambda conn, coin_key, observations: (len(observations), 0))
    monkeypatch.setattr(ingest.time, "sleep", lambda seconds: None)

    summary = ingest.run_intraday_ingest(conn, ["bitcoin", "ethereum"], retention_days=None)

    assert summary.coins_failed == ["bitcoin"]
    assert summary.observations_loaded == 1


def test_load_observations_deduplicates_via_on_conflict():
    """ON CONFLICT (coin_key, observation_timestamp) DO NOTHING: a duplicate observation must
    count as skipped, not loaded -- this drives idempotency for re-running the same ingest."""

    class _DedupCursor:
        def __init__(self, seen: set):
            self._seen = seen

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params):
            self._last_ts = params[1]

        def fetchone(self):
            if self._last_ts in self._seen:
                return None
            self._seen.add(self._last_ts)
            return (1,)

    class _DedupConn:
        def __init__(self):
            self.seen: set[datetime] = set()

        def cursor(self, **kwargs):
            return _DedupCursor(self.seen)

        def commit(self):
            pass

    conn = _DedupConn()
    obs = _obs()
    inserted1, skipped1 = ingest.load_observations(conn, 42, [obs])
    assert (inserted1, skipped1) == (1, 0)

    # Re-ingesting the exact same observation must be skipped, not double-counted.
    inserted2, skipped2 = ingest.load_observations(conn, 42, [obs])
    assert (inserted2, skipped2) == (0, 1)


def test_fetch_with_retry_gives_up_after_max_attempts(monkeypatch):
    calls = {"count": 0}

    def _always_fails(coin_id, days):
        calls["count"] += 1
        raise CoinGeckoAPIError("persistent failure")

    monkeypatch.setattr(ingest, "fetch_coin_market_chart", _always_fails)
    monkeypatch.setattr(ingest.time, "sleep", lambda seconds: None)

    with pytest.raises(CoinGeckoAPIError):
        ingest.fetch_with_retry("bitcoin", 1, max_retries=3)

    assert calls["count"] == 3
