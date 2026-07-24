from datetime import date, timedelta

import pytest

from etl import backfill_market_history as backfill
from integrations.coingecko import CoinGeckoAccessRestrictedError, CoinGeckoAPIError, CoinHistorySnapshot


class _FakeCursor:
    def __init__(self, run_id: int = 1):
        self.run_id = run_id

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return (self.run_id,)


class _FakeConn:
    """Stands in for a psycopg3 Connection: run_backfill only touches conn.cursor()/commit()
    directly for the audit.etl_run bookkeeping — everything per-(coin,date) is monkeypatched at
    the module level (fact_exists/fetch_with_retry/load_one_day), so no real SQL runs here."""

    def cursor(self, **kwargs):
        return _FakeCursor()

    def commit(self):
        pass


def _snapshot(price: float = 100.0) -> CoinHistorySnapshot:
    return CoinHistorySnapshot(id="bitcoin", symbol="btc", name="Bitcoin", current_price=price)


# ---------------------------------------------------------------------------
# Date-range parsing
# ---------------------------------------------------------------------------


def test_parse_date_range_days_ends_today():
    args = type("Args", (), {"days": 3, "start_date": None, "end_date": None})()

    start, end = backfill._parse_date_range(args)

    assert end == date.today()
    assert (end - start).days == 2  # 3 calendar days inclusive


def test_parse_date_range_rejects_days_with_explicit_dates():
    args = type("Args", (), {"days": 3, "start_date": "2026-01-01", "end_date": None})()

    with pytest.raises(SystemExit):
        backfill._parse_date_range(args)


def test_parse_date_range_rejects_start_after_end():
    args = type("Args", (), {"days": None, "start_date": "2026-02-01", "end_date": "2026-01-01"})()

    with pytest.raises(SystemExit):
        backfill._parse_date_range(args)


def test_parse_date_range_explicit_dates():
    args = type("Args", (), {"days": None, "start_date": "2026-01-01", "end_date": "2026-01-05"})()

    start, end = backfill._parse_date_range(args)

    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 5)


# ---------------------------------------------------------------------------
# Retry / rate-limit behavior
# ---------------------------------------------------------------------------


def test_fetch_with_retry_succeeds_after_transient_failures(monkeypatch):
    calls = {"count": 0}

    def _flaky(coin_id, on_date):
        calls["count"] += 1
        if calls["count"] < 3:
            raise CoinGeckoAPIError("transient failure")
        return _snapshot()

    monkeypatch.setattr(backfill, "fetch_coin_history", _flaky)
    monkeypatch.setattr(backfill.time, "sleep", lambda seconds: None)

    result = backfill.fetch_with_retry("bitcoin", date(2026, 1, 1), max_retries=3)

    assert result.current_price == 100.0
    assert calls["count"] == 3


def test_fetch_with_retry_gives_up_after_max_attempts(monkeypatch):
    calls = {"count": 0}

    def _always_fails(coin_id, on_date):
        calls["count"] += 1
        raise CoinGeckoAPIError("persistent failure")

    monkeypatch.setattr(backfill, "fetch_coin_history", _always_fails)
    monkeypatch.setattr(backfill.time, "sleep", lambda seconds: None)

    with pytest.raises(CoinGeckoAPIError):
        backfill.fetch_with_retry("bitcoin", date(2026, 1, 1), max_retries=3)

    assert calls["count"] == 3


def test_fetch_with_retry_does_not_retry_access_restricted_errors(monkeypatch):
    """A 401/403 (outside the free tier's history window) is a permanent rejection of this exact
    request, not a transient failure — retrying wastes attempts and rate-limit budget."""
    calls = {"count": 0}

    def _restricted(coin_id, on_date):
        calls["count"] += 1
        raise CoinGeckoAccessRestrictedError("401 outside allowed window")

    monkeypatch.setattr(backfill, "fetch_coin_history", _restricted)
    monkeypatch.setattr(backfill.time, "sleep", lambda seconds: None)

    with pytest.raises(CoinGeckoAccessRestrictedError):
        backfill.fetch_with_retry("bitcoin", date(2026, 1, 1), max_retries=3)

    assert calls["count"] == 1


# ---------------------------------------------------------------------------
# run_backfill: idempotency, duplicate-date skipping, failure handling
# ---------------------------------------------------------------------------


def test_run_backfill_skips_already_loaded_dates_without_calling_api(monkeypatch):
    """Idempotency + resumability: a (coin, date) pair already present in the warehouse must be
    skipped before any CoinGecko call is made."""
    monkeypatch.setattr(backfill, "fact_exists", lambda conn, coin_id, on_date: True)

    def _fail_if_called(coin_id, on_date, max_retries):
        raise AssertionError("must not call the API for a date that's already loaded")

    monkeypatch.setattr(backfill, "fetch_with_retry", _fail_if_called)
    monkeypatch.setattr(backfill.time, "sleep", lambda seconds: None)

    summary = backfill.run_backfill(
        _FakeConn(), ["bitcoin"], date(2026, 1, 1), date(2026, 1, 3), request_delay_seconds=0
    )

    assert summary.dates_skipped == 3
    assert summary.dates_loaded == 0
    assert summary.dates_failed == 0


def test_run_backfill_loads_missing_dates(monkeypatch):
    monkeypatch.setattr(backfill, "fact_exists", lambda conn, coin_id, on_date: False)
    monkeypatch.setattr(backfill, "fetch_with_retry", lambda coin_id, on_date, max_retries: _snapshot())
    monkeypatch.setattr(backfill, "load_one_day", lambda conn, run_id, coin_id, on_date, snapshot: True)
    monkeypatch.setattr(backfill.time, "sleep", lambda seconds: None)

    summary = backfill.run_backfill(
        _FakeConn(), ["bitcoin"], date(2026, 1, 1), date(2026, 1, 2), request_delay_seconds=0
    )

    assert summary.dates_loaded == 2
    assert summary.dates_skipped == 0
    assert summary.dates_failed == 0


def test_run_backfill_continues_past_failed_dates_and_records_them(monkeypatch):
    """A retryable failure on one (coin, date) pair must not abort the whole run."""
    monkeypatch.setattr(backfill, "fact_exists", lambda conn, coin_id, on_date: False)

    def _fails_on_the_second_day(coin_id, on_date, max_retries):
        if on_date == date(2026, 1, 2):
            raise CoinGeckoAPIError("boom")
        return _snapshot()

    monkeypatch.setattr(backfill, "fetch_with_retry", _fails_on_the_second_day)
    monkeypatch.setattr(backfill, "load_one_day", lambda conn, run_id, coin_id, on_date, snapshot: True)
    monkeypatch.setattr(backfill.time, "sleep", lambda seconds: None)

    summary = backfill.run_backfill(
        _FakeConn(), ["bitcoin"], date(2026, 1, 1), date(2026, 1, 3), request_delay_seconds=0
    )

    assert summary.dates_loaded == 2
    assert summary.dates_failed == 1
    assert summary.failed_pairs == [("bitcoin", date(2026, 1, 2))]


def test_run_backfill_treats_no_coingecko_data_as_skip_not_failure(monkeypatch):
    """fetch_with_retry returning None means CoinGecko genuinely has no data for that day (e.g.
    predates the coin's listing) — a real, non-error outcome, not a failure to retry."""
    monkeypatch.setattr(backfill, "fact_exists", lambda conn, coin_id, on_date: False)
    monkeypatch.setattr(backfill, "fetch_with_retry", lambda coin_id, on_date, max_retries: None)
    monkeypatch.setattr(backfill.time, "sleep", lambda seconds: None)

    summary = backfill.run_backfill(
        _FakeConn(), ["bitcoin"], date(2026, 1, 1), date(2026, 1, 1), request_delay_seconds=0
    )

    assert summary.dates_skipped == 1
    assert summary.dates_loaded == 0
    assert summary.dates_failed == 0


def test_parse_date_range_days_90():
    args = type("Args", (), {"days": 90, "start_date": None, "end_date": None})()

    start, end = backfill._parse_date_range(args)

    assert end == date.today()
    assert (end - start).days == 89  # 90 calendar days inclusive


def test_run_backfill_90_days_skips_already_loaded_dates_without_calling_api(monkeypatch):
    """A 90-day request must skip every already-loaded date before calling CoinGecko for it --
    same idempotency guarantee as any other range, just at the wider width this feature adds."""
    monkeypatch.setattr(backfill, "fact_exists", lambda conn, coin_id, on_date: True)

    def _fail_if_called(coin_id, on_date, max_retries):
        raise AssertionError("must not call the API for a date that's already loaded")

    monkeypatch.setattr(backfill, "fetch_with_retry", _fail_if_called)
    monkeypatch.setattr(backfill.time, "sleep", lambda seconds: None)

    end = date(2026, 7, 23)
    start = end - timedelta(days=89)
    summary = backfill.run_backfill(_FakeConn(), ["bitcoin"], start, end, request_delay_seconds=0)

    assert summary.dates_skipped == 90
    assert summary.dates_loaded == 0


def test_run_backfill_resumes_after_partial_completion(monkeypatch):
    """Simulates an interrupted run: the first invocation loads some dates and fails on others;
    a second invocation over the same range must skip everything the first one actually loaded
    (not just everything it attempted), and only retry what's still missing."""
    loaded_dates: set[date] = set()

    def _fact_exists(conn, coin_id, on_date):
        return on_date in loaded_dates

    def _fetch(coin_id, on_date, max_retries):
        if on_date == date(2026, 1, 2):
            raise CoinGeckoAPIError("transient outage")
        return _snapshot()

    def _load_one_day(conn, run_id, coin_id, on_date, snapshot):
        loaded_dates.add(on_date)
        return True

    monkeypatch.setattr(backfill, "fact_exists", _fact_exists)
    monkeypatch.setattr(backfill, "fetch_with_retry", _fetch)
    monkeypatch.setattr(backfill, "load_one_day", _load_one_day)
    monkeypatch.setattr(backfill.time, "sleep", lambda seconds: None)

    start, end = date(2026, 1, 1), date(2026, 1, 3)

    first = backfill.run_backfill(_FakeConn(), ["bitcoin"], start, end, request_delay_seconds=0)
    assert first.dates_loaded == 2
    assert first.dates_failed == 1
    assert loaded_dates == {date(2026, 1, 1), date(2026, 1, 3)}

    # Second run: 2026-01-02 now succeeds (outage over); the other two must be skipped, not refetched.
    monkeypatch.setattr(
        backfill,
        "fetch_with_retry",
        lambda coin_id, on_date, max_retries: _snapshot() if on_date == date(2026, 1, 2) else (_ for _ in ()).throw(
            AssertionError("must not refetch an already-loaded date")
        ),
    )
    second = backfill.run_backfill(_FakeConn(), ["bitcoin"], start, end, request_delay_seconds=0)

    assert second.dates_loaded == 1
    assert second.dates_skipped == 2
    assert second.dates_failed == 0
    assert loaded_dates == {date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)}


def test_run_backfill_duplicate_fact_row_counts_as_skip(monkeypatch):
    """load_one_day returning False (ON CONFLICT DO NOTHING at the fact grain) must still count
    as skipped, not loaded, so the summary reflects rows actually inserted."""
    monkeypatch.setattr(backfill, "fact_exists", lambda conn, coin_id, on_date: False)
    monkeypatch.setattr(backfill, "fetch_with_retry", lambda coin_id, on_date, max_retries: _snapshot())
    monkeypatch.setattr(backfill, "load_one_day", lambda conn, run_id, coin_id, on_date, snapshot: False)
    monkeypatch.setattr(backfill.time, "sleep", lambda seconds: None)

    summary = backfill.run_backfill(
        _FakeConn(), ["bitcoin"], date(2026, 1, 1), date(2026, 1, 1), request_delay_seconds=0
    )

    assert summary.dates_loaded == 0
    assert summary.dates_skipped == 1
