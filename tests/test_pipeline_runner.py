import threading
import time
from datetime import date

import pytest

from services import pipeline_runner
from etl.load_warehouse import ETLResult
from etl.ingest_market_data import IngestResult


class _FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeConn:
    def close(self) -> None:
        pass

    def cursor(self):
        return _FakeCursor()

    def commit(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _reset_state():
    """Each test starts from a clean lock/state, regardless of execution order."""
    pipeline_runner._state.currently_running = False
    pipeline_runner._state.last_success_at = None
    pipeline_runner._state.last_failure_at = None
    pipeline_runner._state.last_error_message = None
    yield


def test_run_pipeline_success_updates_state(monkeypatch):
    monkeypatch.setattr(pipeline_runner, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(
        pipeline_runner,
        "run_ingest",
        lambda conn, currency, limit, order: IngestResult(run_id=1, rows_inserted=5),
    )
    monkeypatch.setattr(
        pipeline_runner,
        "run_etl",
        lambda conn, run_id: ETLResult(
            etl_run_id=2,
            staging_run_id=1,
            snapshot_date=date(2026, 7, 23),
            dim_date_inserted=0,
            dim_coin_inserted=0,
            dim_coin_updated=0,
            fact_inserted=5,
            elapsed_seconds=0.01,
        ),
    )

    summary = pipeline_runner.run_pipeline("manual")

    assert summary.status == "succeeded"
    assert summary.ingest.rows_inserted == 5
    assert summary.etl.fact_inserted == 5

    state = pipeline_runner.get_state_snapshot()
    assert state["currently_running"] is False
    assert state["last_success_at"] is not None
    assert state["last_failure_at"] is None


def test_run_pipeline_failure_updates_state(monkeypatch):
    from etl.ingest_market_data import IngestError

    monkeypatch.setattr(pipeline_runner, "get_connection", lambda: _FakeConn())

    def _raise_ingest(conn, currency, limit, order):
        raise IngestError(run_id=1, message="CoinGecko unreachable")

    monkeypatch.setattr(pipeline_runner, "run_ingest", _raise_ingest)

    summary = pipeline_runner.run_pipeline("scheduled")

    assert summary.status == "failed"
    assert "CoinGecko unreachable" in summary.error_message

    state = pipeline_runner.get_state_snapshot()
    assert state["currently_running"] is False
    assert state["last_failure_at"] is not None
    assert state["last_error_message"] == summary.error_message


def test_run_pipeline_with_intraday_prunes_old_rows(monkeypatch):
    """The manual "Take New Snapshot" path (insert_intraday=True) must prune old intraday rows
    just like the standalone ingest_intraday_market_data.py CLI job does -- otherwise a warehouse
    relying only on this button grows dw.fact_market_intraday unbounded."""
    monkeypatch.setattr(pipeline_runner, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(
        pipeline_runner,
        "run_ingest",
        lambda conn, currency, limit, order: IngestResult(run_id=1, rows_inserted=5),
    )
    monkeypatch.setattr(
        pipeline_runner,
        "run_etl",
        lambda conn, run_id: ETLResult(
            etl_run_id=2,
            staging_run_id=1,
            snapshot_date=date(2026, 7, 23),
            dim_date_inserted=0,
            dim_coin_inserted=0,
            dim_coin_updated=0,
            fact_inserted=5,
            elapsed_seconds=0.01,
        ),
    )
    monkeypatch.setattr(pipeline_runner, "insert_intraday_from_staging", lambda cur, run_id, ts: 5)

    prune_calls = []

    def _fake_prune(conn, retention_days):
        prune_calls.append(retention_days)
        return 12

    monkeypatch.setattr(pipeline_runner, "prune_old_intraday", _fake_prune)

    summary = pipeline_runner.run_pipeline("manual", insert_intraday=True)

    assert summary.status == "succeeded"
    assert summary.intraday_snapshots_inserted == 5
    assert summary.intraday_rows_pruned == 12
    assert prune_calls == [pipeline_runner.DEFAULT_RETENTION_DAYS]


def test_concurrent_run_is_skipped(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def _slow_ingest(conn, currency, limit, order):
        started.set()
        release.wait(timeout=5)
        return IngestResult(run_id=1, rows_inserted=1)

    monkeypatch.setattr(pipeline_runner, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(pipeline_runner, "run_ingest", _slow_ingest)
    monkeypatch.setattr(pipeline_runner, "run_etl", lambda conn, run_id: None)

    thread = threading.Thread(target=pipeline_runner.run_pipeline, args=("scheduled",))
    thread.start()
    assert started.wait(timeout=5), "background run never started"

    assert pipeline_runner.get_state_snapshot()["currently_running"] is True

    with pytest.raises(pipeline_runner.PipelineAlreadyRunningError):
        pipeline_runner.run_pipeline("manual")

    release.set()
    thread.join(timeout=5)

    assert pipeline_runner.get_state_snapshot()["currently_running"] is False
