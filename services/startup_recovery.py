import threading
from datetime import date, datetime, timedelta, timezone

from etl import backfill_market_history
from config.app_timezone import today as app_today
from database import get_connection
from utils.logging_config import get_logger

"""Startup gap-detection and non-blocking historical backfill (Parts 7-9, 13-14).

On FastAPI startup, compares the newest date actually loaded in the daily warehouse fact table
(dw.fact_market_snapshot) against "today" (app_timezone.today()) and backfills every complete
calendar date in between -- through the *existing* backfill_market_history.run_backfill pipeline,
never a second ingestion system. "Today" itself is deliberately never backfilled here: it's
populated by normal ingestion / the manual snapshot button (see pipeline_runner.py), matching
Part 9's policy that an in-progress day is never mistaken for a complete closing snapshot.

Never blocks the FastAPI startup path: start_recovery_if_needed() does two fast, indexed
SELECTs synchronously (to decide whether anything needs backfilling and to report an immediate
"nothing to do" or "already running elsewhere" status) and then hands the actual multi-day
backfill to a background daemon thread.

Safe under Uvicorn `--reload` (which can execute startup code in more than one process): a
Postgres advisory lock (session-scoped, released automatically when the lock-holding connection
closes) ensures only one process's background thread ever runs the backfill at a time. A second
process that can't acquire the lock simply reports status "running" without starting a duplicate.
"""

logger = get_logger("startup_recovery")

# Arbitrary fixed key identifying "the startup recovery job" in Postgres's advisory-lock
# namespace. Any distinct bigint works; it just needs to be the same constant every time so every
# process contends for the same lock.
ADVISORY_LOCK_KEY = 7_931_004_215

_state_lock = threading.Lock()


class _RecoveryState:
    def __init__(self) -> None:
        self.status = "idle"  # idle | running | completed | partial_failure | failed
        self.last_daily_snapshot_date: date | None = None
        self.expected_latest_daily_date: date | None = None
        self.missing_dates: list[date] = []
        self.dates_completed: list[date] = []
        self.current_date_processing: date | None = None
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.errors: list[str] = []


_state = _RecoveryState()


def get_state_snapshot() -> dict:
    """Sanitized status snapshot for GET /admin/data-recovery-status -- string error messages
    only, never tracebacks."""
    with _state_lock:
        return {
            "status": _state.status,
            "last_daily_snapshot_date": _state.last_daily_snapshot_date,
            "expected_latest_daily_date": _state.expected_latest_daily_date,
            "missing_dates": list(_state.missing_dates),
            "dates_completed": list(_state.dates_completed),
            "current_date_processing": _state.current_date_processing,
            "started_at": _state.started_at,
            "completed_at": _state.completed_at,
            "errors": list(_state.errors),
        }


def get_latest_daily_date(conn) -> date | None:
    """Newest calendar date actually loaded in the daily warehouse fact table."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT max(d.full_date) FROM dw.fact_market_snapshot f JOIN dw.dim_date d ON d.date_key = f.date_key"
        )
        row = cur.fetchone()
        return row[0] if row else None


def get_tracked_coin_ids(conn) -> list[str]:
    """Coin ids to backfill: every currently-tracked coin (dw.dim_coin.is_current)."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT coin_id FROM dw.dim_coin WHERE is_current ORDER BY coin_id")
        return [row[0] for row in cur.fetchall()]


def compute_missing_dates(latest: date | None, today: date) -> list[date]:
    """Every completed calendar date strictly between `latest` and `today`, inclusive of both
    ends of that gap. `today` itself is never included -- it's populated by normal
    ingestion/the manual snapshot button, not backfill (Part 9). If `latest` is None (an empty
    warehouse), there is no baseline to backfill from, so this returns [] and normal ingestion
    establishes the first day."""
    if latest is None:
        return []
    end = today - timedelta(days=1)
    if latest >= end:
        return []
    missing = []
    d = latest + timedelta(days=1)
    while d <= end:
        missing.append(d)
        d += timedelta(days=1)
    return missing


def _run_recovery(missing_dates: list[date], lock_conn) -> None:
    """Runs on a background daemon thread. Backfills each missing date in chronological order via
    the existing backfill_market_history.run_backfill, continuing to the next date after a
    failure (Part 14) rather than aborting the whole run. Releases the advisory lock (by closing
    lock_conn, which drops every session-level lock it holds) when done, regardless of outcome."""
    work_conn = get_connection()
    try:
        coins = get_tracked_coin_ids(work_conn)
        if not coins:
            logger.warning("Startup recovery: no tracked coins in dw.dim_coin yet; nothing to backfill")
        else:
            for on_date in missing_dates:
                with _state_lock:
                    _state.current_date_processing = on_date
                try:
                    summary = backfill_market_history.run_backfill(work_conn, coins, on_date, on_date)
                except Exception as exc:
                    logger.exception("Startup recovery: unexpected error backfilling %s", on_date)
                    with _state_lock:
                        _state.errors.append(f"{on_date}: {exc}")
                    continue

                if summary.failed_pairs:
                    failed_coins = ", ".join(c for c, _ in summary.failed_pairs[:10])
                    with _state_lock:
                        _state.errors.append(
                            f"{on_date}: {len(summary.failed_pairs)} coin(s) failed after retries: {failed_coins}"
                        )

                # A date counts as recovered if at least one coin actually loaded, or if nothing
                # failed at all (e.g. every coin was already loaded, or CoinGecko genuinely has no
                # data for that day -- both legitimate, non-error outcomes of run_backfill).
                if summary.dates_loaded > 0 or summary.dates_failed == 0:
                    with _state_lock:
                        _state.dates_completed.append(on_date)

                logger.info(
                    "Startup recovery: %s done (loaded=%d skipped=%d failed=%d)",
                    on_date,
                    summary.dates_loaded,
                    summary.dates_skipped,
                    summary.dates_failed,
                )
    finally:
        work_conn.close()
        with _state_lock:
            _state.current_date_processing = None
            _state.completed_at = datetime.now(timezone.utc)
            _state.status = (
                "completed" if len(_state.dates_completed) == len(missing_dates) else "partial_failure"
            )
        lock_conn.close()  # releases the Postgres session-level advisory lock


def start_recovery_if_needed() -> None:
    """Call once from FastAPI's lifespan startup. Never raises: any failure to even reach the
    database is caught, logged, and recorded as status "failed" so the rest of the app still
    starts normally (this also keeps it safe to call in test/dev environments with no database
    configured)."""
    try:
        conn = get_connection()
        try:
            latest = get_latest_daily_date(conn)
            today = app_today()
            missing = compute_missing_dates(latest, today)
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Startup recovery: could not determine missing dates: %s", exc)
        with _state_lock:
            _state.status = "failed"
            _state.errors = [str(exc)]
        return

    with _state_lock:
        _state.last_daily_snapshot_date = latest
        _state.expected_latest_daily_date = today - timedelta(days=1) if latest is not None else None
        _state.missing_dates = missing

    if not missing:
        with _state_lock:
            _state.status = "completed"
            _state.completed_at = datetime.now(timezone.utc)
        logger.info("Startup recovery: no missing daily dates (latest=%s)", latest)
        return

    try:
        lock_conn = get_connection()
        lock_conn.autocommit = True
        with lock_conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
            acquired = cur.fetchone()[0]
    except Exception as exc:
        logger.warning("Startup recovery: could not acquire advisory lock: %s", exc)
        with _state_lock:
            _state.status = "failed"
            _state.errors = [str(exc)]
        return

    if not acquired:
        lock_conn.close()
        with _state_lock:
            _state.status = "running"
        logger.info(
            "Startup recovery: %d missing date(s), but another process already holds the recovery "
            "lock -- skipping duplicate run",
            len(missing),
        )
        return

    with _state_lock:
        _state.status = "running"
        _state.started_at = datetime.now(timezone.utc)
        _state.dates_completed = []
        _state.errors = []

    logger.info("Startup recovery: backfilling %d missing date(s): %s .. %s", len(missing), missing[0], missing[-1])
    thread = threading.Thread(target=_run_recovery, args=(missing, lock_conn), daemon=True, name="startup-recovery")
    thread.start()
