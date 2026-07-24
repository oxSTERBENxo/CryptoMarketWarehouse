from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from api import admin_routes
from etl.load_warehouse import ETLResult
from etl.ingest_market_data import IngestResult
from main import app
from services.pipeline_runner import PipelineAlreadyRunningError, PipelineRunSummary


def test_run_etl_now_returns_summary(monkeypatch):
    now = datetime.now(timezone.utc)
    summary = PipelineRunSummary(
        trigger="manual",
        status="succeeded",
        started_at=now,
        finished_at=now,
        elapsed_seconds=1.23,
        ingest=IngestResult(run_id=1, rows_inserted=5),
        etl=ETLResult(
            etl_run_id=2,
            staging_run_id=1,
            snapshot_date=date(2026, 7, 23),
            dim_date_inserted=0,
            dim_coin_inserted=0,
            dim_coin_updated=0,
            fact_inserted=5,
            elapsed_seconds=0.5,
        ),
    )
    monkeypatch.setattr(admin_routes, "run_pipeline", lambda **kwargs: summary)

    with TestClient(app) as client:
        response = client.post("/admin/run-etl")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["ingest"]["rows_inserted"] == 5
    assert body["etl"]["fact_inserted"] == 5


def test_run_etl_now_returns_409_when_already_running(monkeypatch):
    def _raise(**kwargs):
        raise PipelineAlreadyRunningError("A pipeline run is already in progress")

    monkeypatch.setattr(admin_routes, "run_pipeline", _raise)

    with TestClient(app) as client:
        response = client.post("/admin/run-etl")

    assert response.status_code == 409


def test_refresh_market_data_returns_reshaped_summary(monkeypatch):
    now = datetime.now(timezone.utc)
    summary = PipelineRunSummary(
        trigger="manual",
        status="succeeded",
        started_at=now,
        finished_at=now,
        elapsed_seconds=2.5,
        ingest=IngestResult(run_id=1, rows_inserted=100),
        etl=ETLResult(
            etl_run_id=2,
            staging_run_id=1,
            snapshot_date=date(2026, 7, 24),
            dim_date_inserted=1,
            dim_coin_inserted=3,
            dim_coin_updated=2,
            fact_inserted=100,
            elapsed_seconds=1.1,
        ),
        intraday_snapshots_inserted=100,
    )
    monkeypatch.setattr(admin_routes, "run_pipeline", lambda **kwargs: summary)
    monkeypatch.setattr(
        admin_routes.startup_recovery,
        "get_state_snapshot",
        lambda: {"missing_dates": [], "dates_completed": []},
    )
    monkeypatch.setattr(admin_routes, "fetch_intraday_count_today", lambda conn: 7)

    with TestClient(app) as client:
        response = client.post("/admin/refresh-market-data")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["coins_fetched"] == 100
    assert body["staging_rows_inserted"] == 100
    assert body["daily_snapshots_inserted"] == 100
    assert body["intraday_snapshots_inserted"] == 100
    assert body["coins_updated"] == 5
    assert body["missing_dates_found"] == 0
    assert body["dates_backfilled"] == 0
    assert body["intraday_snapshots_today"] == 7
    assert body["refreshed_at"] is not None
    assert body["errors"] == []


def test_refresh_market_data_reports_zero_new_daily_snapshots_on_repeat_run(monkeypatch):
    """Same-day re-press: coins are still fetched and staged (coins_fetched/staging_rows_inserted
    > 0), but the warehouse's ON CONFLICT (date_key, coin_key) DO NOTHING guard means no new daily
    row lands (daily_snapshots_inserted == 0, coins_updated == 0) -- this is what the dashboard
    uses to show "New intraday snapshot added; today's daily snapshot already existed." while a
    new intraday row (intraday_snapshots_inserted > 0) is still created every press."""
    now = datetime.now(timezone.utc)
    summary = PipelineRunSummary(
        trigger="manual",
        status="succeeded",
        started_at=now,
        finished_at=now,
        elapsed_seconds=1.0,
        ingest=IngestResult(run_id=3, rows_inserted=100),
        etl=ETLResult(
            etl_run_id=4,
            staging_run_id=3,
            snapshot_date=date(2026, 7, 24),
            dim_date_inserted=0,
            dim_coin_inserted=0,
            dim_coin_updated=0,
            fact_inserted=0,
            elapsed_seconds=0.2,
        ),
        intraday_snapshots_inserted=100,
    )
    monkeypatch.setattr(admin_routes, "run_pipeline", lambda **kwargs: summary)
    monkeypatch.setattr(
        admin_routes.startup_recovery,
        "get_state_snapshot",
        lambda: {"missing_dates": [], "dates_completed": []},
    )
    monkeypatch.setattr(admin_routes, "fetch_intraday_count_today", lambda conn: 2)

    with TestClient(app) as client:
        response = client.post("/admin/refresh-market-data")

    assert response.status_code == 200
    body = response.json()
    assert body["coins_fetched"] == 100
    assert body["staging_rows_inserted"] == 100
    assert body["daily_snapshots_inserted"] == 0
    assert body["intraday_snapshots_inserted"] == 100
    assert body["coins_updated"] == 0


def test_refresh_market_data_repeated_presses_create_distinct_intraday_runs(monkeypatch):
    """Part 17 item 18/Part 16 item 15: repeated same-day manual presses each report their own
    intraday_snapshots_inserted rather than 0 on the second call."""
    now = datetime.now(timezone.utc)

    def _summary(intraday_count: int) -> PipelineRunSummary:
        return PipelineRunSummary(
            trigger="manual",
            status="succeeded",
            started_at=now,
            finished_at=now,
            elapsed_seconds=1.0,
            ingest=IngestResult(run_id=1, rows_inserted=100),
            etl=ETLResult(
                etl_run_id=1,
                staging_run_id=1,
                snapshot_date=date(2026, 7, 24),
                dim_date_inserted=0,
                dim_coin_inserted=0,
                dim_coin_updated=0,
                fact_inserted=0,
                elapsed_seconds=0.1,
            ),
            intraday_snapshots_inserted=intraday_count,
        )

    monkeypatch.setattr(
        admin_routes.startup_recovery,
        "get_state_snapshot",
        lambda: {"missing_dates": [], "dates_completed": []},
    )
    monkeypatch.setattr(admin_routes, "fetch_intraday_count_today", lambda conn: 1)

    monkeypatch.setattr(admin_routes, "run_pipeline", lambda **kwargs: _summary(100))
    with TestClient(app) as client:
        first = client.post("/admin/refresh-market-data").json()

    monkeypatch.setattr(admin_routes, "fetch_intraday_count_today", lambda conn: 2)
    monkeypatch.setattr(admin_routes, "run_pipeline", lambda **kwargs: _summary(100))
    with TestClient(app) as client:
        second = client.post("/admin/refresh-market-data").json()

    assert first["intraday_snapshots_inserted"] == 100
    assert second["intraday_snapshots_inserted"] == 100
    assert first["intraday_snapshots_today"] == 1
    assert second["intraday_snapshots_today"] == 2
    assert first["daily_snapshots_inserted"] == 0
    assert second["daily_snapshots_inserted"] == 0


def test_refresh_market_data_returns_409_when_already_running(monkeypatch):
    def _raise(**kwargs):
        raise PipelineAlreadyRunningError("A pipeline run is already in progress")

    monkeypatch.setattr(admin_routes, "run_pipeline", _raise)

    with TestClient(app) as client:
        response = client.post("/admin/refresh-market-data")

    assert response.status_code == 409


def test_refresh_market_data_reports_error_message_on_failure(monkeypatch):
    now = datetime.now(timezone.utc)
    summary = PipelineRunSummary(
        trigger="manual",
        status="failed",
        started_at=now,
        finished_at=now,
        elapsed_seconds=0.5,
        ingest=None,
        etl=None,
        error_message="CoinGecko unreachable",
    )
    monkeypatch.setattr(admin_routes, "run_pipeline", lambda **kwargs: summary)
    monkeypatch.setattr(
        admin_routes.startup_recovery,
        "get_state_snapshot",
        lambda: {"missing_dates": [], "dates_completed": []},
    )

    with TestClient(app) as client:
        response = client.post("/admin/refresh-market-data")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["coins_fetched"] == 0
    assert body["staging_rows_inserted"] == 0
    assert body["daily_snapshots_inserted"] == 0
    assert body["intraday_snapshots_inserted"] == 0
    assert body["coins_updated"] == 0
    assert body["intraday_snapshots_today"] == 0
    assert body["errors"] == ["CoinGecko unreachable"]


def test_health_scheduler_reports_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_SCHEDULER", raising=False)

    with TestClient(app) as client:
        response = client.get("/health/scheduler")

    assert response.status_code == 200
    body = response.json()
    assert "enabled" in body
    assert "running" in body
    assert "currently_running" in body
    assert "next_run_time" in body
    assert "last_success_at" in body
    assert "last_failure_at" in body
