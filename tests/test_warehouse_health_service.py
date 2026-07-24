from datetime import date, datetime, timedelta, timezone

import pytest

from health import service as whs


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._one = None
        self._all: list = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=()):
        text = " ".join(sql.split())
        self.conn.executed.append(text)

        if text == "SELECT 1":
            self._one = (1,)
        elif "FROM audit.etl_run WHERE status = %s" in text:
            self._one = self.conn.latest_runs.get(params[0])
        elif text == "SELECT max(observation_timestamp) FROM dw.fact_market_intraday":
            self._one = (self.conn.last_hourly_snapshot_at,)
        elif "GROUP BY date_key, coin_key HAVING" in text:
            self._one = (self.conn.daily_dupes,)
        elif "GROUP BY coin_key, observation_timestamp HAVING" in text:
            self._one = (self.conn.intraday_dupes,)
        elif text == "SELECT count(*) FROM dw.fact_market_snapshot":
            self._one = (self.conn.daily_fact_row_count,)
        elif text == "SELECT count(*) FROM dw.fact_market_intraday":
            self._one = (self.conn.hourly_fact_row_count,)
        elif text == "SELECT count(*) FROM dw.dim_coin WHERE is_current":
            self._one = (self.conn.current_coin_count,)
        elif text == "SELECT count(*) FROM dw.dim_coin WHERE NOT is_current":
            self._one = (self.conn.historical_coin_version_count,)
        elif "FROM audit.etl_run WHERE status = 'failed' AND started_at" in text:
            self._one = (self.conn.recent_failed_run_count,)
        elif "FROM dw.dim_coin dc" in text:
            self._all = self.conn.stale_coin_rows
        else:
            raise AssertionError(f"unexpected SQL in warehouse_health_service test fake: {text}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


class _FakeConn:
    def __init__(self, **overrides):
        self.executed: list[str] = []
        self.latest_runs: dict = overrides.get("latest_runs", {})
        self.last_hourly_snapshot_at = overrides.get("last_hourly_snapshot_at")
        self.daily_dupes = overrides.get("daily_dupes", 0)
        self.intraday_dupes = overrides.get("intraday_dupes", 0)
        self.daily_fact_row_count = overrides.get("daily_fact_row_count", 0)
        self.hourly_fact_row_count = overrides.get("hourly_fact_row_count", 0)
        self.current_coin_count = overrides.get("current_coin_count", 0)
        self.historical_coin_version_count = overrides.get("historical_coin_version_count", 0)
        self.recent_failed_run_count = overrides.get("recent_failed_run_count", 0)
        self.stale_coin_rows = overrides.get("stale_coin_rows", [])
        self.db_error = overrides.get("db_error")

    def cursor(self):
        if self.db_error:
            raise self.db_error
        return _FakeCursor(self)


def _default_scheduler_status(**overrides):
    status = {
        "enabled": False,
        "running": False,
        "interval_minutes": 60,
        "currently_running": False,
        "last_success_at": None,
        "last_failure_at": None,
        "next_run_time": None,
        "intraday_enabled": False,
        "intraday_interval_minutes": 60,
        "intraday_next_run_time": None,
    }
    status.update(overrides)
    return status


@pytest.fixture(autouse=True)
def _clean_defaults(monkeypatch):
    """Every test starts from a "nothing wrong" baseline unless it overrides these."""
    monkeypatch.setattr(whs.scheduler, "get_scheduler_status", lambda: _default_scheduler_status())
    monkeypatch.setattr(whs.startup_recovery, "get_latest_daily_date", lambda conn: date(2026, 7, 24))
    monkeypatch.setattr(whs.startup_recovery, "compute_missing_dates", lambda latest, today: [])


def test_database_unreachable_yields_error_overall_status_and_unknown_checks():
    conn = _FakeConn(db_error=RuntimeError("connection refused"))

    result = whs.get_warehouse_health(conn)

    assert result.database.status == "error"
    assert result.overall_status == "error"
    assert result.data_quality.status == "unknown"
    assert result.duplicate_check.status == "unknown"
    assert result.missing_date_coverage.status == "unknown"
    assert result.stale_coin_check.status == "unknown"
    assert result.daily_fact_row_count == 0
    assert result.latest_successful_run is None


def test_all_clean_yields_healthy_overall_status():
    conn = _FakeConn(
        latest_runs={
            "succeeded": (72, "coingecko_warehouse_load", "succeeded", datetime(2026, 7, 24, tzinfo=timezone.utc), datetime(2026, 7, 24, tzinfo=timezone.utc), None),
        },
        daily_fact_row_count=1246,
        hourly_fact_row_count=2696,
        current_coin_count=103,
        historical_coin_version_count=0,
        recent_failed_run_count=0,
        daily_dupes=0,
        intraday_dupes=0,
        stale_coin_rows=[],
    )

    result = whs.get_warehouse_health(conn)

    assert result.overall_status == "healthy"
    assert result.latest_successful_run.run_id == 72
    assert result.latest_failed_run is None
    assert result.daily_fact_row_count == 1246
    assert result.data_quality.status == "healthy"
    assert result.duplicate_check.status == "healthy"
    assert result.missing_date_coverage.status == "healthy"
    assert result.stale_coin_check.status == "healthy"


def test_recent_failures_yield_data_quality_warning():
    conn = _FakeConn(recent_failed_run_count=3)

    result = whs.get_warehouse_health(conn)

    assert result.data_quality.status == "warning"
    assert "3 failed" in result.data_quality.message
    assert result.overall_status == "warning"


def test_duplicate_facts_yield_error_overall_status():
    """This should be impossible under the UNIQUE constraints -- if it's ever nonzero, that's a
    real, serious problem, not a warning."""
    conn = _FakeConn(daily_dupes=2)

    result = whs.get_warehouse_health(conn)

    assert result.duplicate_check.status == "error"
    assert result.overall_status == "error"


def test_missing_dates_yield_warning(monkeypatch):
    monkeypatch.setattr(
        whs.startup_recovery,
        "compute_missing_dates",
        lambda latest, today: [date(2026, 7, 22), date(2026, 7, 23)],
    )
    conn = _FakeConn()

    result = whs.get_warehouse_health(conn)

    assert result.missing_date_coverage.status == "warning"
    assert result.missing_dates == [date(2026, 7, 22), date(2026, 7, 23)]
    assert result.overall_status == "warning"


def test_stale_coins_yield_warning():
    conn = _FakeConn(stale_coin_rows=[("dogecoin", "DOGE", date(2026, 7, 10))])

    result = whs.get_warehouse_health(conn)

    assert result.stale_coin_check.status == "warning"
    assert len(result.stale_coins) == 1
    assert result.stale_coins[0].symbol == "DOGE"
    assert result.overall_status == "warning"


def test_scheduler_disabled_is_reported_healthy_not_a_warning(monkeypatch):
    """A disabled scheduler is the documented default (manual snapshots/backfill instead) -- it
    must not read as a problem on a freshly set-up demo environment."""
    monkeypatch.setattr(whs.scheduler, "get_scheduler_status", lambda: _default_scheduler_status(enabled=False))
    conn = _FakeConn()

    result = whs.get_warehouse_health(conn)

    assert result.scheduler.status == "healthy"


def test_scheduler_enabled_but_not_running_is_a_warning(monkeypatch):
    monkeypatch.setattr(
        whs.scheduler, "get_scheduler_status", lambda: _default_scheduler_status(enabled=True, running=False)
    )
    conn = _FakeConn()

    result = whs.get_warehouse_health(conn)

    assert result.scheduler.status == "warning"
    assert result.overall_status == "warning"


def test_scheduler_enabled_and_running_is_healthy(monkeypatch):
    monkeypatch.setattr(
        whs.scheduler, "get_scheduler_status", lambda: _default_scheduler_status(enabled=True, running=True)
    )
    conn = _FakeConn()

    result = whs.get_warehouse_health(conn)

    assert result.scheduler.status == "healthy"


def test_worst_picks_the_most_severe_status():
    from health.models import HealthCheck

    assert whs._worst(HealthCheck(status="healthy", message=""), HealthCheck(status="warning", message="")) == "warning"
    assert (
        whs._worst(
            HealthCheck(status="warning", message=""),
            HealthCheck(status="error", message=""),
            HealthCheck(status="unknown", message=""),
        )
        == "error"
    )
    assert whs._worst(HealthCheck(status="healthy", message="")) == "healthy"
