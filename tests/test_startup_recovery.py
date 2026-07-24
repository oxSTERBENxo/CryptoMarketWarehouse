from dataclasses import dataclass, field
from datetime import date

import pytest

from services import startup_recovery


# ---------------------------------------------------------------------------
# compute_missing_dates: pure function, deterministic date-boundary behavior (Part 16 items 7-10, 20)
# ---------------------------------------------------------------------------

TODAY = date(2026, 7, 24)


def test_no_missing_dates_when_latest_is_yesterday():
    """Part 9: today itself is never backfilled -- it's populated by normal ingestion."""
    assert startup_recovery.compute_missing_dates(date(2026, 7, 23), TODAY) == []


def test_no_missing_dates_when_latest_is_today():
    assert startup_recovery.compute_missing_dates(TODAY, TODAY) == []


def test_one_missing_date():
    # latest = today - 2 -> exactly one complete missing day (today - 1)
    assert startup_recovery.compute_missing_dates(date(2026, 7, 22), TODAY) == [date(2026, 7, 23)]


def test_three_missing_dates_backfilled_in_chronological_order():
    assert startup_recovery.compute_missing_dates(date(2026, 7, 20), TODAY) == [
        date(2026, 7, 21),
        date(2026, 7, 22),
        date(2026, 7, 23),
    ]


def test_week_missing_backfills_entire_gap():
    assert startup_recovery.compute_missing_dates(date(2026, 7, 16), TODAY) == [
        date(2026, 7, 17),
        date(2026, 7, 18),
        date(2026, 7, 19),
        date(2026, 7, 20),
        date(2026, 7, 21),
        date(2026, 7, 22),
        date(2026, 7, 23),
    ]


def test_empty_warehouse_has_no_baseline_to_backfill_from():
    assert startup_recovery.compute_missing_dates(None, TODAY) == []


# ---------------------------------------------------------------------------
# Fakes for exercising start_recovery_if_needed / _run_recovery without a real database or thread
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._result = None
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append(sql.strip().splitlines()[0])
        if "pg_try_advisory_lock" in sql:
            self._result = (self.conn.lock_acquired,)
        elif "max(d.full_date)" in sql:
            self._result = (self.conn.latest_date,)
        elif "DISTINCT coin_id" in sql:
            self._rows = [(c,) for c in self.conn.coins]
        else:
            self._result = None

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._rows


@dataclass
class _FakeConn:
    latest_date: date | None = None
    coins: list[str] = field(default_factory=lambda: ["bitcoin"])
    lock_acquired: bool = True
    executed: list = field(default_factory=list)
    autocommit: bool = False
    closed: bool = False

    def cursor(self):
        return _FakeCursor(self)

    def close(self):
        self.closed = True


class _SyncThread:
    """Runs the target synchronously in start(), so tests don't need real threading/joins."""

    instances: list["_SyncThread"] = []

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        _SyncThread.instances.append(self)

    def start(self):
        self.target(*self.args, **self.kwargs)


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Each test gets a clean module-level _state and a fresh _SyncThread spy list."""
    monkeypatch.setattr(startup_recovery, "_state", startup_recovery._RecoveryState())
    _SyncThread.instances = []
    monkeypatch.setattr(startup_recovery.threading, "Thread", _SyncThread)
    # startup_recovery imports `today` from app_timezone as `app_today`.
    monkeypatch.setattr(startup_recovery, "app_today", lambda: TODAY)
    yield


def test_startup_with_no_missing_dates_starts_no_backfill(monkeypatch):
    conn = _FakeConn(latest_date=TODAY)
    monkeypatch.setattr(startup_recovery, "get_connection", lambda: conn)

    startup_recovery.start_recovery_if_needed()

    snapshot = startup_recovery.get_state_snapshot()
    assert snapshot["status"] == "completed"
    assert snapshot["missing_dates"] == []
    assert _SyncThread.instances == []


def test_startup_with_one_missing_day_backfills_exactly_one(monkeypatch):
    conns = [_FakeConn(latest_date=date(2026, 7, 22)), _FakeConn(lock_acquired=True), _FakeConn(coins=["bitcoin"])]
    monkeypatch.setattr(startup_recovery, "get_connection", lambda: conns.pop(0))

    calls = []

    def _fake_run_backfill(conn, coins, start_date, end_date):
        calls.append((start_date, end_date))
        return _summary(dates_loaded=1)

    monkeypatch.setattr(startup_recovery.backfill_market_history, "run_backfill", _fake_run_backfill)

    startup_recovery.start_recovery_if_needed()

    snapshot = startup_recovery.get_state_snapshot()
    assert calls == [(date(2026, 7, 23), date(2026, 7, 23))]
    assert snapshot["dates_completed"] == [date(2026, 7, 23)]
    assert snapshot["status"] == "completed"


def test_startup_with_three_missing_days_backfills_all_three_in_order(monkeypatch):
    conns = [_FakeConn(latest_date=date(2026, 7, 20)), _FakeConn(lock_acquired=True), _FakeConn(coins=["bitcoin"])]
    monkeypatch.setattr(startup_recovery, "get_connection", lambda: conns.pop(0))

    calls = []
    monkeypatch.setattr(
        startup_recovery.backfill_market_history,
        "run_backfill",
        lambda conn, coins, start_date, end_date: (calls.append(start_date), _summary(dates_loaded=1))[1],
    )

    startup_recovery.start_recovery_if_needed()

    assert calls == [date(2026, 7, 21), date(2026, 7, 22), date(2026, 7, 23)]
    snapshot = startup_recovery.get_state_snapshot()
    assert snapshot["dates_completed"] == calls
    assert snapshot["status"] == "completed"


def test_startup_with_a_week_missing_backfills_entire_gap(monkeypatch):
    conns = [_FakeConn(latest_date=date(2026, 7, 16)), _FakeConn(lock_acquired=True), _FakeConn(coins=["bitcoin"])]
    monkeypatch.setattr(startup_recovery, "get_connection", lambda: conns.pop(0))

    calls = []
    monkeypatch.setattr(
        startup_recovery.backfill_market_history,
        "run_backfill",
        lambda conn, coins, start_date, end_date: (calls.append(start_date), _summary(dates_loaded=1))[1],
    )

    startup_recovery.start_recovery_if_needed()

    assert len(calls) == 7
    snapshot = startup_recovery.get_state_snapshot()
    assert snapshot["status"] == "completed"
    assert len(snapshot["dates_completed"]) == 7


def test_restart_after_successful_backfill_creates_no_duplicates(monkeypatch):
    """Once the warehouse's latest date has caught up to yesterday, a second startup call must
    not invoke run_backfill again -- idempotent restart."""
    conn = _FakeConn(latest_date=date(2026, 7, 23))
    monkeypatch.setattr(startup_recovery, "get_connection", lambda: conn)

    calls = []
    monkeypatch.setattr(
        startup_recovery.backfill_market_history,
        "run_backfill",
        lambda *a, **k: calls.append(1) or _summary(dates_loaded=1),
    )

    startup_recovery.start_recovery_if_needed()

    assert calls == []
    assert startup_recovery.get_state_snapshot()["status"] == "completed"


def test_partially_existing_day_is_skipped_not_reloaded(monkeypatch):
    """A day where every (coin, date) pair already exists (run_backfill skips them all) still
    counts as recovered -- no failures, nothing to retry."""
    conns = [_FakeConn(latest_date=date(2026, 7, 22)), _FakeConn(lock_acquired=True), _FakeConn(coins=["bitcoin"])]
    monkeypatch.setattr(startup_recovery, "get_connection", lambda: conns.pop(0))
    monkeypatch.setattr(
        startup_recovery.backfill_market_history,
        "run_backfill",
        lambda *a, **k: _summary(dates_loaded=0, dates_skipped=1, dates_failed=0),
    )

    startup_recovery.start_recovery_if_needed()

    snapshot = startup_recovery.get_state_snapshot()
    assert snapshot["dates_completed"] == [date(2026, 7, 23)]
    assert snapshot["status"] == "completed"


def test_concurrent_startup_workers_create_only_one_recovery_job(monkeypatch):
    """Simulates a second Uvicorn --reload worker: the advisory lock is already held elsewhere, so
    this process must not spawn a background thread of its own."""
    conns = [_FakeConn(latest_date=date(2026, 7, 22)), _FakeConn(lock_acquired=False)]
    monkeypatch.setattr(startup_recovery, "get_connection", lambda: conns.pop(0))

    def _fail_if_called(*a, **k):
        raise AssertionError("run_backfill must not be called when the lock isn't acquired")

    monkeypatch.setattr(startup_recovery.backfill_market_history, "run_backfill", _fail_if_called)

    startup_recovery.start_recovery_if_needed()

    assert _SyncThread.instances == []
    assert startup_recovery.get_state_snapshot()["status"] == "running"


def test_partial_backfill_error_is_reported_accurately_and_later_dates_still_attempted(monkeypatch):
    """Part 14: July 21 succeeds, July 22 fails, July 23 is still attempted (continues, doesn't
    abort); recovery is not marked complete while a gap remains."""
    conns = [_FakeConn(latest_date=date(2026, 7, 20)), _FakeConn(lock_acquired=True), _FakeConn(coins=["bitcoin"])]
    monkeypatch.setattr(startup_recovery, "get_connection", lambda: conns.pop(0))

    def _run_backfill(conn, coins, start_date, end_date):
        if start_date == date(2026, 7, 22):
            return _summary(dates_loaded=0, dates_failed=1, failed_pairs=[("bitcoin", start_date)])
        return _summary(dates_loaded=1)

    monkeypatch.setattr(startup_recovery.backfill_market_history, "run_backfill", _run_backfill)

    startup_recovery.start_recovery_if_needed()

    snapshot = startup_recovery.get_state_snapshot()
    assert snapshot["dates_completed"] == [date(2026, 7, 21), date(2026, 7, 23)]
    assert snapshot["status"] == "partial_failure"
    assert any("2026-07-22" in e for e in snapshot["errors"])


def test_recovery_status_endpoint_reports_running_state(monkeypatch):
    startup_recovery._state.status = "running"
    startup_recovery._state.missing_dates = [date(2026, 7, 23)]
    startup_recovery._state.dates_completed = []

    snapshot = startup_recovery.get_state_snapshot()

    assert snapshot["status"] == "running"
    assert snapshot["missing_dates"] == [date(2026, 7, 23)]


def test_recovery_status_endpoint_reports_completed_state(monkeypatch):
    startup_recovery._state.status = "completed"
    startup_recovery._state.missing_dates = []

    snapshot = startup_recovery.get_state_snapshot()

    assert snapshot["status"] == "completed"


def test_startup_recovery_never_raises_when_database_is_unreachable(monkeypatch):
    def _raise():
        raise ConnectionError("could not connect to server")

    monkeypatch.setattr(startup_recovery, "get_connection", _raise)

    startup_recovery.start_recovery_if_needed()  # must not raise

    snapshot = startup_recovery.get_state_snapshot()
    assert snapshot["status"] == "failed"
    assert "could not connect to server" in snapshot["errors"][0]


def _summary(dates_loaded=0, dates_skipped=0, dates_failed=0, failed_pairs=None):
    return startup_recovery.backfill_market_history.BackfillSummary(
        run_id=1,
        coins=["bitcoin"],
        start_date=TODAY,
        end_date=TODAY,
        dates_skipped=dates_skipped,
        dates_loaded=dates_loaded,
        dates_failed=dates_failed,
        failed_pairs=failed_pairs or [],
    )
