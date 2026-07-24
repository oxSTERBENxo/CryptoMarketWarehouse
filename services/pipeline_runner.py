import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from config import app_timezone
from database import get_connection
from etl.load_warehouse import ETLError, ETLResult, insert_intraday_from_staging, run_etl
from etl.ingest_intraday_market_data import DEFAULT_RETENTION_DAYS, prune_old_intraday
from etl.ingest_market_data import IngestError, IngestResult, run_ingest
from utils.logging_config import get_logger

logger = get_logger("pipeline_runner")

_run_lock = threading.Lock()
_state_lock = threading.Lock()


class PipelineAlreadyRunningError(Exception):
    """Raised when a pipeline run is requested while another one is already in progress."""


@dataclass
class PipelineRunSummary:
    trigger: str
    status: str  # "succeeded" | "failed"
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float
    ingest: IngestResult | None = None
    etl: ETLResult | None = None
    intraday_snapshots_inserted: int = 0
    intraday_rows_pruned: int = 0
    error_message: str | None = None


class _SchedulerState:
    """Tracks pipeline execution state for the health endpoint. Guarded by _state_lock."""

    def __init__(self) -> None:
        self.currently_running: bool = False
        self.last_success_at: datetime | None = None
        self.last_failure_at: datetime | None = None
        self.last_error_message: str | None = None


_state = _SchedulerState()


def get_state_snapshot() -> dict:
    with _state_lock:
        return {
            "currently_running": _state.currently_running,
            "last_success_at": _state.last_success_at,
            "last_failure_at": _state.last_failure_at,
            "last_error_message": _state.last_error_message,
        }


def run_pipeline(
    trigger: str,
    currency: str = "usd",
    limit: int = 100,
    order: str = "market_cap_desc",
    insert_intraday: bool = False,
) -> PipelineRunSummary:
    """Run one full CoinGecko ingest -> ETL cycle, reusing the existing ingest/ETL entry points.

    Enforces mutual exclusion across scheduled and manual triggers: if a run is already in
    progress, raises PipelineAlreadyRunningError instead of running concurrently.

    `insert_intraday=True` (Part 10, used only by the manual "Take New Snapshot" button --
    scheduled runs and /admin/run-etl keep the default False, unchanged) additionally lands one
    dw.fact_market_intraday row per successfully-fetched coin, all sharing a single timestamp
    captured for this run, reusing the same staging rows the ingest step already fetched -- no
    extra CoinGecko call.
    """
    if not _run_lock.acquire(blocking=False):
        logger.warning("Skipping %s pipeline run: a pipeline run is already in progress", trigger)
        raise PipelineAlreadyRunningError("A pipeline run is already in progress")

    with _state_lock:
        _state.currently_running = True

    started_at = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()
    logger.info("Pipeline run started (trigger=%s)", trigger)

    conn = get_connection()
    ingest_result: IngestResult | None = None
    etl_result: ETLResult | None = None
    intraday_snapshots_inserted = 0
    intraday_rows_pruned = 0
    try:
        try:
            ingest_result = run_ingest(conn, currency=currency, limit=limit, order=order)
            logger.info(
                "Ingestion completed (trigger=%s): run_id=%s rows_inserted=%d",
                trigger,
                ingest_result.run_id,
                ingest_result.rows_inserted,
            )

            etl_result = run_etl(conn, run_id=ingest_result.run_id)
            if etl_result is not None:
                logger.info(
                    "ETL completed (trigger=%s): etl_run_id=%s fact_inserted=%d elapsed=%.2fs",
                    trigger,
                    etl_result.etl_run_id,
                    etl_result.fact_inserted,
                    etl_result.elapsed_seconds,
                )

            if insert_intraday:
                observation_timestamp = app_timezone.now()
                with conn.cursor() as cur:
                    intraday_snapshots_inserted = insert_intraday_from_staging(
                        cur, ingest_result.run_id, observation_timestamp
                    )
                conn.commit()
                logger.info(
                    "Intraday snapshot recorded (trigger=%s): run_id=%s observations=%d timestamp=%s",
                    trigger,
                    ingest_result.run_id,
                    intraday_snapshots_inserted,
                    observation_timestamp,
                )
                # The standalone etl/ingest_intraday_market_data.py CLI job prunes after every run, but
                # this manual "Take New Snapshot" path used to skip pruning entirely, so a warehouse
                # relying only on this button would grow dw.fact_market_intraday unbounded.
                intraday_rows_pruned = prune_old_intraday(conn, DEFAULT_RETENTION_DAYS)
                if intraday_rows_pruned:
                    logger.info(
                        "Pruned %d intraday row(s) older than %d day(s) (trigger=%s)",
                        intraday_rows_pruned,
                        DEFAULT_RETENTION_DAYS,
                        trigger,
                    )
        except (IngestError, ETLError) as exc:
            elapsed = time.monotonic() - started_monotonic
            finished_at = datetime.now(timezone.utc)
            logger.error("Pipeline run failed (trigger=%s) after %.2fs: %s", trigger, elapsed, exc)
            with _state_lock:
                _state.last_failure_at = finished_at
                _state.last_error_message = str(exc)
            return PipelineRunSummary(
                trigger=trigger,
                status="failed",
                started_at=started_at,
                finished_at=finished_at,
                elapsed_seconds=elapsed,
                ingest=ingest_result,
                etl=etl_result,
                error_message=str(exc),
            )
        finally:
            conn.close()

        elapsed = time.monotonic() - started_monotonic
        finished_at = datetime.now(timezone.utc)
        logger.info("Pipeline run succeeded (trigger=%s) in %.2fs", trigger, elapsed)
        with _state_lock:
            _state.last_success_at = finished_at
            _state.last_error_message = None
        return PipelineRunSummary(
            trigger=trigger,
            status="succeeded",
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=elapsed,
            ingest=ingest_result,
            etl=etl_result,
            intraday_snapshots_inserted=intraday_snapshots_inserted,
            intraday_rows_pruned=intraday_rows_pruned,
        )
    finally:
        with _state_lock:
            _state.currently_running = False
        _run_lock.release()
