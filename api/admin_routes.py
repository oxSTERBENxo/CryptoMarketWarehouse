from fastapi import APIRouter, HTTPException

from services import startup_recovery
from analytics.repository import fetch_intraday_count_today
from database import get_connection
from services.pipeline_runner import PipelineAlreadyRunningError, run_pipeline
from services.scheduler import SCHEDULER_CURRENCY, SCHEDULER_LIMIT, SCHEDULER_ORDER

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/data-recovery-status",
    summary="Startup gap-detection / historical backfill status",
    description=(
        "Reports the status of the non-blocking startup recovery job that backfills any daily "
        "warehouse dates missed while the app was down (see startup_recovery.py): idle (nothing "
        "checked yet), running, completed, partial_failure (some dates could not be backfilled), "
        "or failed (could not even determine what was missing, e.g. database unavailable at "
        "startup). Error messages are sanitized strings, never stack traces."
    ),
)
def get_data_recovery_status() -> dict:
    return startup_recovery.get_state_snapshot()


@router.post(
    "/run-etl",
    summary="Manually trigger one ingest + ETL pipeline run",
    description=(
        "Runs one full CoinGecko ingest -> ETL cycle immediately, using the same reused "
        "components as the scheduler. Does not interfere with or replace scheduled execution. "
        "Returns 409 if a pipeline run (scheduled or manual) is already in progress."
    ),
)
def run_etl_now() -> dict:
    try:
        summary = run_pipeline(
            trigger="manual",
            currency=SCHEDULER_CURRENCY,
            limit=SCHEDULER_LIMIT,
            order=SCHEDULER_ORDER,
        )
    except PipelineAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "trigger": summary.trigger,
        "status": summary.status,
        "started_at": summary.started_at,
        "finished_at": summary.finished_at,
        "elapsed_seconds": round(summary.elapsed_seconds, 2),
        "ingest": (
            {"run_id": summary.ingest.run_id, "rows_inserted": summary.ingest.rows_inserted}
            if summary.ingest
            else None
        ),
        "etl": (
            {
                "etl_run_id": summary.etl.etl_run_id,
                "staging_run_id": summary.etl.staging_run_id,
                "snapshot_date": summary.etl.snapshot_date,
                "fact_inserted": summary.etl.fact_inserted,
                "dim_coin_inserted": summary.etl.dim_coin_inserted,
                "dim_coin_updated": summary.etl.dim_coin_updated,
            }
            if summary.etl
            else None
        ),
        "error_message": summary.error_message,
    }


@router.post(
    "/refresh-market-data",
    summary="Manually run the incremental ingestion pipeline and report what changed",
    description=(
        "Runs the same incremental ingest -> ETL cycle as /admin/run-etl (never a historical "
        "backfill, never a data wipe), plus one new dw.fact_market_intraday observation per "
        "successfully-fetched coin (Part 10) -- so every successful press creates a distinctly "
        "timestamped intraday snapshot even when daily_snapshots_inserted is 0 (today's daily row "
        "already existed). The response distinguishes source data fetched from CoinGecko "
        "(coins_fetched), rows landed in the staging table (staging_rows_inserted), new daily "
        "warehouse fact rows (daily_snapshots_inserted), new intraday fact rows "
        "(intraday_snapshots_inserted), and dw.dim_coin SCD2 changes (coins_updated) -- these are "
        "separate concepts that can diverge (e.g. a same-day re-press still fetches/stages fresh "
        "prices and adds an intraday row even though the warehouse's (date_key, coin_key) "
        "idempotency guard means daily_snapshots_inserted == 0). missing_dates_found/"
        "dates_backfilled/dates_skipped reflect the startup recovery job's state at call time (see "
        "GET /admin/data-recovery-status), not anything this endpoint itself backfills. Returns "
        "409 if a pipeline run (scheduled or manual) is already in progress."
    ),
)
def refresh_market_data() -> dict:
    try:
        summary = run_pipeline(
            trigger="manual",
            currency=SCHEDULER_CURRENCY,
            limit=SCHEDULER_LIMIT,
            order=SCHEDULER_ORDER,
            insert_intraday=True,
        )
    except PipelineAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    recovery = startup_recovery.get_state_snapshot()

    intraday_snapshots_today = 0
    if summary.status == "succeeded":
        conn = get_connection()
        try:
            intraday_snapshots_today = fetch_intraday_count_today(conn)
        finally:
            conn.close()

    return {
        "status": summary.status,
        "coins_fetched": summary.ingest.rows_inserted if summary.ingest else 0,
        "staging_rows_inserted": summary.ingest.rows_inserted if summary.ingest else 0,
        "daily_snapshots_inserted": summary.etl.fact_inserted if summary.etl else 0,
        "intraday_snapshots_inserted": summary.intraday_snapshots_inserted,
        "coins_updated": (
            (summary.etl.dim_coin_inserted + summary.etl.dim_coin_updated) if summary.etl else 0
        ),
        "missing_dates_found": len(recovery["missing_dates"]),
        "dates_backfilled": len(recovery["dates_completed"]),
        "dates_skipped": 0,
        "elapsed_seconds": round(summary.elapsed_seconds, 2),
        "refreshed_at": summary.finished_at,
        "intraday_snapshots_today": intraday_snapshots_today,
        "errors": [summary.error_message] if summary.error_message else [],
    }
