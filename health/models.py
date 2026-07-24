from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

# "unknown" covers a check that couldn't run at all (e.g. the database is unreachable, so
# everything downstream of it is unknown rather than a guessed "healthy"/"error").
HealthState = Literal["healthy", "warning", "error", "unknown"]


class HealthCheck(BaseModel):
    """One deterministic check with a plain-English reason -- the page never shows a bare
    status without explaining why."""

    status: HealthState
    message: str


class EtlRunInfo(BaseModel):
    run_id: int
    pipeline_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None = None


class StaleCoin(BaseModel):
    """A currently-tracked coin whose most recent daily fact row is more than
    warehouse_health_service.STALE_COIN_THRESHOLD_DAYS behind the warehouse's overall latest
    date -- or has no daily fact row at all yet."""

    coin_id: str
    symbol: str
    last_seen_date: date | None


class WarehouseHealthResponse(BaseModel):
    generated_at: datetime
    environment: str
    overall_status: HealthState

    database: HealthCheck
    latest_successful_run: EtlRunInfo | None
    latest_failed_run: EtlRunInfo | None

    last_daily_snapshot_date: date | None
    last_hourly_snapshot_at: datetime | None
    daily_fact_row_count: int
    hourly_fact_row_count: int
    current_coin_count: int
    historical_coin_version_count: int

    recent_failed_run_count: int
    data_quality: HealthCheck
    duplicate_check: HealthCheck

    missing_date_coverage: HealthCheck
    missing_dates: list[date]

    stale_coin_check: HealthCheck
    stale_coins: list[StaleCoin]

    scheduler: HealthCheck
    scheduler_status: dict
