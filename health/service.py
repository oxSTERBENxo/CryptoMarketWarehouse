import os
from datetime import date, datetime, timedelta, timezone

from psycopg import Connection

from services import scheduler
from services import startup_recovery
from config.app_timezone import today as app_today
from health.models import (
    EtlRunInfo,
    HealthCheck,
    StaleCoin,
    WarehouseHealthResponse,
)

"""Aggregates deterministic warehouse/ETL health signals into one response for the Warehouse
Health page -- database connectivity, ETL run history, fact/dimension row counts, a duplicate-key
check, missing-date coverage, and stale-coin detection. Every figure here is a plain read query or
a reuse of an existing helper (startup_recovery.get_latest_daily_date/compute_missing_dates,
scheduler.get_scheduler_status) -- nothing here mutates the database. Never returns connection
strings, credentials, or any other secret-shaped value."""

STALE_COIN_THRESHOLD_DAYS = 3
RECENT_FAILURE_WINDOW_DAYS = 7

_STATUS_SEVERITY: dict[str, int] = {"healthy": 0, "unknown": 1, "warning": 2, "error": 3}


def _worst(*checks: HealthCheck) -> str:
    return max((c.status for c in checks), key=lambda status: _STATUS_SEVERITY[status])


def _unavailable(message: str = "Not checked: database unavailable.") -> HealthCheck:
    return HealthCheck(status="unknown", message=message)


def _check_database(conn: Connection) -> HealthCheck:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return HealthCheck(status="healthy", message="Connected.")
    except Exception as exc:
        return HealthCheck(status="error", message=f"Database connection failed: {exc}")


def _fetch_latest_run(conn: Connection, status: str) -> EtlRunInfo | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT run_id, pipeline_name, status, started_at, finished_at, error_message
            FROM audit.etl_run
            WHERE status = %s
            ORDER BY finished_at DESC NULLS LAST, started_at DESC
            LIMIT 1
            """,
            (status,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    run_id, pipeline_name, run_status, started_at, finished_at, error_message = row
    return EtlRunInfo(
        run_id=run_id,
        pipeline_name=pipeline_name,
        status=run_status,
        started_at=started_at,
        finished_at=finished_at,
        error_message=error_message,
    )


def _scalar(conn: Connection, sql: str, params: tuple = ()) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def _fetch_last_hourly_snapshot(conn: Connection) -> datetime | None:
    with conn.cursor() as cur:
        cur.execute("SELECT max(observation_timestamp) FROM dw.fact_market_intraday")
        row = cur.fetchone()
        return row[0] if row else None


def _duplicate_check(conn: Connection) -> HealthCheck:
    """Both fact tables' grain is a real DB UNIQUE constraint, so this should always find zero --
    this check exists to verify that invariant actually holds (e.g. against a constraint dropped
    outside the normal migration path), not because duplicates are expected."""
    daily_dupes = _scalar(
        conn,
        "SELECT count(*) FROM (SELECT 1 FROM dw.fact_market_snapshot GROUP BY date_key, coin_key HAVING count(*) > 1) d",
    )
    intraday_dupes = _scalar(
        conn,
        "SELECT count(*) FROM (SELECT 1 FROM dw.fact_market_intraday GROUP BY coin_key, observation_timestamp HAVING count(*) > 1) d",
    )
    if daily_dupes or intraday_dupes:
        return HealthCheck(
            status="error",
            message=(
                f"Found {daily_dupes} duplicate daily fact key(s) and {intraday_dupes} duplicate "
                "intraday fact key(s) -- this should be impossible under the UNIQUE constraints and "
                "means they were bypassed."
            ),
        )
    return HealthCheck(status="healthy", message="No duplicate fact rows found for either grain.")


def _stale_coins(conn: Connection, latest_date: date | None) -> list[StaleCoin]:
    """Currently-tracked coins that have fallen behind the warehouse's overall latest loaded date
    by more than STALE_COIN_THRESHOLD_DAYS, or have no daily fact row at all yet."""
    if latest_date is None:
        return []
    threshold = latest_date - timedelta(days=STALE_COIN_THRESHOLD_DAYS)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT dc.coin_id, dc.symbol, max(d.full_date) AS last_seen
            FROM dw.dim_coin dc
            LEFT JOIN dw.fact_market_snapshot f ON f.coin_key = dc.coin_key
            LEFT JOIN dw.dim_date d ON d.date_key = f.date_key
            WHERE dc.is_current
            GROUP BY dc.coin_id, dc.symbol
            HAVING max(d.full_date) IS NULL OR max(d.full_date) < %s
            ORDER BY max(d.full_date) NULLS FIRST, dc.symbol
            """,
            (threshold,),
        )
        rows = cur.fetchall()
    return [StaleCoin(coin_id=coin_id, symbol=symbol, last_seen_date=last_seen) for coin_id, symbol, last_seen in rows]


def _scheduler_check(status: dict) -> HealthCheck:
    if not status["enabled"]:
        return HealthCheck(
            status="healthy",
            message="Scheduler disabled (ENABLE_SCHEDULER=false) -- expected when relying on manual snapshots/backfill.",
        )
    if not status["running"]:
        return HealthCheck(
            status="warning",
            message="Scheduler is enabled but not currently running -- it may need a restart.",
        )
    return HealthCheck(status="healthy", message=f"Running, every {status['interval_minutes']} minute(s).")


def get_warehouse_health(conn: Connection) -> WarehouseHealthResponse:
    generated_at = datetime.now(timezone.utc)
    environment = os.environ.get("ENVIRONMENT", "development")
    database_check = _check_database(conn)
    scheduler_status = scheduler.get_scheduler_status()
    scheduler_check = _scheduler_check(scheduler_status)

    if database_check.status != "healthy":
        # Nothing else here can be safely queried if the connection itself is down.
        return WarehouseHealthResponse(
            generated_at=generated_at,
            environment=environment,
            overall_status=_worst(database_check, scheduler_check),
            database=database_check,
            latest_successful_run=None,
            latest_failed_run=None,
            last_daily_snapshot_date=None,
            last_hourly_snapshot_at=None,
            daily_fact_row_count=0,
            hourly_fact_row_count=0,
            current_coin_count=0,
            historical_coin_version_count=0,
            recent_failed_run_count=0,
            data_quality=_unavailable(),
            duplicate_check=_unavailable(),
            missing_date_coverage=_unavailable(),
            missing_dates=[],
            stale_coin_check=_unavailable(),
            stale_coins=[],
            scheduler=scheduler_check,
            scheduler_status=scheduler_status,
        )

    latest_successful_run = _fetch_latest_run(conn, "succeeded")
    latest_failed_run = _fetch_latest_run(conn, "failed")
    last_daily_snapshot_date = startup_recovery.get_latest_daily_date(conn)
    last_hourly_snapshot_at = _fetch_last_hourly_snapshot(conn)
    daily_fact_row_count = _scalar(conn, "SELECT count(*) FROM dw.fact_market_snapshot")
    hourly_fact_row_count = _scalar(conn, "SELECT count(*) FROM dw.fact_market_intraday")
    current_coin_count = _scalar(conn, "SELECT count(*) FROM dw.dim_coin WHERE is_current")
    historical_coin_version_count = _scalar(conn, "SELECT count(*) FROM dw.dim_coin WHERE NOT is_current")

    recent_failed_run_count = _scalar(
        conn,
        "SELECT count(*) FROM audit.etl_run WHERE status = 'failed' AND started_at >= now() - (%s * INTERVAL '1 day')",
        (RECENT_FAILURE_WINDOW_DAYS,),
    )
    data_quality = (
        HealthCheck(status="healthy", message=f"No failed pipeline runs in the last {RECENT_FAILURE_WINDOW_DAYS} days.")
        if recent_failed_run_count == 0
        else HealthCheck(
            status="warning",
            message=f"{recent_failed_run_count} failed pipeline run(s) in the last {RECENT_FAILURE_WINDOW_DAYS} days.",
        )
    )

    duplicate_check = _duplicate_check(conn)

    missing_dates = startup_recovery.compute_missing_dates(last_daily_snapshot_date, app_today())
    missing_date_coverage = (
        HealthCheck(status="healthy", message="No gaps between the last loaded date and today.")
        if not missing_dates
        else HealthCheck(
            status="warning",
            message=f"{len(missing_dates)} day(s) missing between {missing_dates[0]} and {missing_dates[-1]}.",
        )
    )

    stale_coins = _stale_coins(conn, last_daily_snapshot_date)
    stale_coin_check = (
        HealthCheck(status="healthy", message="Every tracked coin has a recent daily snapshot.")
        if not stale_coins
        else HealthCheck(
            status="warning",
            message=f"{len(stale_coins)} tracked coin(s) have no daily snapshot in the last {STALE_COIN_THRESHOLD_DAYS} days.",
        )
    )

    return WarehouseHealthResponse(
        generated_at=generated_at,
        environment=environment,
        overall_status=_worst(
            database_check, data_quality, duplicate_check, missing_date_coverage, stale_coin_check, scheduler_check
        ),
        database=database_check,
        latest_successful_run=latest_successful_run,
        latest_failed_run=latest_failed_run,
        last_daily_snapshot_date=last_daily_snapshot_date,
        last_hourly_snapshot_at=last_hourly_snapshot_at,
        daily_fact_row_count=daily_fact_row_count,
        hourly_fact_row_count=hourly_fact_row_count,
        current_coin_count=current_coin_count,
        historical_coin_version_count=historical_coin_version_count,
        recent_failed_run_count=recent_failed_run_count,
        data_quality=data_quality,
        duplicate_check=duplicate_check,
        missing_date_coverage=missing_date_coverage,
        missing_dates=missing_dates,
        stale_coin_check=stale_coin_check,
        stale_coins=stale_coins,
        scheduler=scheduler_check,
        scheduler_status=scheduler_status,
    )
