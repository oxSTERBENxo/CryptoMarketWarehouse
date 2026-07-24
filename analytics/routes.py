from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from analytics import repository as repo
from analytics.models import (
    CoinHistorySummary,
    CoinSnapshot,
    CurrentMarketSnapshot,
    IntradaySnapshot,
    MarketLeadersCoverage,
    MarketLeadersResponse,
    MarketLeadersSummary,
    MarketMoverEntry,
    MarketOverview,
    TopMarketCapEntry,
    TopVolumeEntry,
)
from database import get_connection

router = APIRouter(prefix="/analytics", tags=["analytics"])


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


def _get_db():
    """Yield a connection for one request; convert a failure to *connect* into a 503.

    Only `get_connection()` itself is guarded: FastAPI enters this generator before request
    validation runs, and re-throws validation failures into it during cleanup. Wrapping the
    `yield` in the same try/except would misreport those (e.g. an out-of-range `limit` or an
    invalid `order`) as 503 instead of the correct 422. The connection still commits on a clean
    return and rolls back if an exception propagates, via psycopg3 Connection's own
    context-manager semantics.
    """
    try:
        conn = get_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    with conn:
        yield conn


DbDep = Annotated[Connection, Depends(_get_db)]


@router.get(
    "/overview",
    response_model=MarketOverview,
    summary="Current market overview",
    description=(
        "Aggregate summary of the most recently loaded snapshot: number of coins tracked, "
        "total market capitalization (USD), and total 24h trading volume (USD). "
        "Backed by `analytics.current_market_overview`. Returns 404 if no snapshot has been loaded yet."
    ),
)
def get_overview(conn: DbDep) -> MarketOverview:
    row = repo.fetch_overview(conn)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No analytics data available yet. Run the ingestion and ETL pipelines to load a snapshot.",
        )
    return MarketOverview.model_validate(row)


@router.get(
    "/latest",
    response_model=list[CoinSnapshot],
    summary="Latest snapshot for every coin",
    description=(
        "One row per coin as of the most recently loaded snapshot date, sorted by market cap. "
        "Backed by `analytics.latest_snapshot`. Returns an empty list if no data has been loaded yet."
    ),
)
def get_latest(
    conn: DbDep,
    limit: Annotated[
        int | None,
        Query(ge=1, le=500, description="Maximum number of coins to return. Omit to return all coins."),
    ] = None,
    order: Annotated[
        SortOrder, Query(description="Sort direction by market cap: 'desc' (largest first) or 'asc'.")
    ] = SortOrder.desc,
) -> list[CoinSnapshot]:
    rows = repo.fetch_latest(conn, limit, order.value)
    return [CoinSnapshot.model_validate(row) for row in rows]


@router.get(
    "/current-market",
    response_model=CurrentMarketSnapshot,
    summary="Live current-market values from the latest ingestion run",
    description=(
        "Aggregate overview plus a per-coin list, sourced from the most recently ingested "
        "staging run (`analytics.current_market_live`) rather than the daily-grain "
        "`analytics.latest_snapshot`. Reflects intraday price/volume/rank changes immediately, "
        "even on a same-day refresh where the warehouse's (date_key, coin_key) idempotency guard "
        "means no new row landed in `dw.fact_market_snapshot`. Backs the main dashboard's "
        "Take New Snapshot refresh. Returns 404 if nothing has been ingested yet."
    ),
)
def get_current_market(
    conn: DbDep,
    limit: Annotated[
        int | None, Query(ge=1, le=500, description="Maximum number of coins to return. Omit to return all coins.")
    ] = None,
    order: Annotated[
        SortOrder, Query(description="Sort direction by market cap: 'desc' (largest first) or 'asc'.")
    ] = SortOrder.desc,
) -> CurrentMarketSnapshot:
    result = repo.fetch_current_market(conn, limit, order.value)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No market data has been ingested yet. Run the ingestion pipeline to load data.",
        )
    return CurrentMarketSnapshot.model_validate(result)


@router.get(
    "/top-market-cap",
    response_model=list[TopMarketCapEntry],
    summary="Coins ranked by market cap",
    description=(
        "Latest snapshot ranked by market capitalization. `market_cap_position` is each coin's "
        "global rank and is unaffected by the requested sort direction or limit. "
        "Backed by `analytics.top_market_cap`."
    ),
)
def get_top_market_cap(
    conn: DbDep,
    limit: Annotated[
        int | None, Query(ge=1, le=500, description="Maximum number of coins to return.")
    ] = 10,
    order: Annotated[
        SortOrder, Query(description="Sort direction by market cap: 'desc' (largest first) or 'asc'.")
    ] = SortOrder.desc,
) -> list[TopMarketCapEntry]:
    rows = repo.fetch_top_market_cap(conn, limit, order.value)
    return [TopMarketCapEntry.model_validate(row) for row in rows]


@router.get(
    "/top-volume",
    response_model=list[TopVolumeEntry],
    summary="Coins ranked by 24h volume",
    description=(
        "Latest snapshot ranked by 24h trading volume. `volume_position` is each coin's global "
        "rank and is unaffected by the requested sort direction or limit. "
        "Backed by `analytics.top_volume`."
    ),
)
def get_top_volume(
    conn: DbDep,
    limit: Annotated[
        int | None, Query(ge=1, le=500, description="Maximum number of coins to return.")
    ] = 10,
    order: Annotated[
        SortOrder, Query(description="Sort direction by volume: 'desc' (largest first) or 'asc'.")
    ] = SortOrder.desc,
) -> list[TopVolumeEntry]:
    rows = repo.fetch_top_volume(conn, limit, order.value)
    return [TopVolumeEntry.model_validate(row) for row in rows]


@router.get(
    "/history/{coin_symbol}",
    response_model=list[CoinSnapshot],
    summary="Historical time series for one coin",
    description=(
        "Full history of loaded snapshots for a single coin, matched case-insensitively by symbol "
        "(e.g. 'btc'). Optionally bounded by `from_date`/`to_date`. Backed by `analytics.market_history`. "
        "Returns 404 if the symbol has never appeared in any loaded snapshot, or an empty list if the "
        "symbol is valid but no rows fall within the requested date range."
    ),
)
def get_history(
    conn: DbDep,
    coin_symbol: str,
    limit: Annotated[
        int | None, Query(ge=1, le=1000, description="Maximum number of rows to return. Omit to return all.")
    ] = None,
    order: Annotated[
        SortOrder, Query(description="Sort direction by snapshot date: 'asc' (chronological) or 'desc'.")
    ] = SortOrder.asc,
    from_date: Annotated[
        date | None, Query(description="Only include snapshots on or after this date (YYYY-MM-DD).")
    ] = None,
    to_date: Annotated[
        date | None, Query(description="Only include snapshots on or before this date (YYYY-MM-DD).")
    ] = None,
) -> list[CoinSnapshot]:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must not be later than to_date")

    if not repo.symbol_has_history(conn, coin_symbol):
        raise HTTPException(status_code=404, detail=f"Unknown coin symbol: {coin_symbol!r}")

    rows = repo.fetch_history(conn, coin_symbol, from_date, to_date, order.value, limit)
    return [CoinSnapshot.model_validate(row) for row in rows]


@router.get(
    "/history/{coin_symbol}/summary",
    response_model=CoinHistorySummary,
    summary="Historical summary statistics for one coin",
    description=(
        "Period summary derived from the same data as `/history/{coin_symbol}`, computed once in "
        "SQL instead of per-request in the frontend: start/end price, absolute/percent change, "
        "min/max/avg price, observation count, and first/latest snapshot dates. Optionally bounded "
        "by `from_date`/`to_date`. Returns 404 if the symbol is unknown, or if it is known but has "
        "no snapshots within the requested date range."
    ),
)
def get_history_summary(
    conn: DbDep,
    coin_symbol: str,
    from_date: Annotated[
        date | None, Query(description="Only include snapshots on or after this date (YYYY-MM-DD).")
    ] = None,
    to_date: Annotated[
        date | None, Query(description="Only include snapshots on or before this date (YYYY-MM-DD).")
    ] = None,
) -> CoinHistorySummary:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must not be later than to_date")

    if not repo.symbol_has_history(conn, coin_symbol):
        raise HTTPException(status_code=404, detail=f"Unknown coin symbol: {coin_symbol!r}")

    row = repo.fetch_history_summary(conn, coin_symbol, from_date, to_date)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"No snapshots for {coin_symbol!r} in the requested date range"
        )
    return CoinHistorySummary.model_validate(row)


@router.get(
    "/intraday/{coin_symbol}",
    response_model=list[IntradaySnapshot],
    summary="Intraday (sub-daily) observations for one coin",
    description=(
        "Sub-daily time series for a single coin, matched case-insensitively by symbol, backed by "
        "`analytics.market_intraday` (dw.fact_market_intraday) -- entirely separate from the daily "
        "`/history/{coin_symbol}` endpoint, which is unchanged. Optionally bounded by "
        "`from_timestamp`/`to_timestamp`. Returns 404 if the symbol is not a tracked coin at all, or "
        "an empty list if the coin is tracked but has no intraday observations loaded "
        "(e.g. `etl/ingest_intraday_market_data.py` has never been run for it)."
    ),
)
def get_intraday(
    conn: DbDep,
    coin_symbol: str,
    limit: Annotated[
        int | None, Query(ge=1, le=2000, description="Maximum number of rows to return. Omit to return all.")
    ] = None,
    order: Annotated[
        SortOrder, Query(description="Sort direction by timestamp: 'asc' (chronological) or 'desc'.")
    ] = SortOrder.asc,
    from_timestamp: Annotated[
        datetime | None, Query(description="Only include observations at or after this UTC timestamp (ISO 8601).")
    ] = None,
    to_timestamp: Annotated[
        datetime | None, Query(description="Only include observations at or before this UTC timestamp (ISO 8601).")
    ] = None,
) -> list[IntradaySnapshot]:
    if from_timestamp is not None and to_timestamp is not None and from_timestamp > to_timestamp:
        raise HTTPException(status_code=400, detail="from_timestamp must not be later than to_timestamp")

    if not repo.symbol_has_intraday(conn, coin_symbol):
        raise HTTPException(status_code=404, detail=f"Unknown coin symbol: {coin_symbol!r}")

    rows = repo.fetch_intraday(conn, coin_symbol, from_timestamp, to_timestamp, order.value, limit)
    return [IntradaySnapshot.model_validate(row) for row in rows]


@router.get(
    "/intraday/{coin_symbol}/today",
    response_model=list[IntradaySnapshot],
    summary="Today's intraday observations for one coin",
    description=(
        "Today's (current UTC calendar date) intraday observations for one coin, sorted "
        "chronologically -- the focused endpoint the Coin Details 'Today' chart uses. Returns 404 "
        "if the symbol is not a tracked coin, or an empty list if no intraday observations have "
        "landed yet today."
    ),
)
def get_intraday_today(conn: DbDep, coin_symbol: str) -> list[IntradaySnapshot]:
    if not repo.symbol_has_intraday(conn, coin_symbol):
        raise HTTPException(status_code=404, detail=f"Unknown coin symbol: {coin_symbol!r}")

    rows = repo.fetch_intraday_today(conn, coin_symbol)
    return [IntradaySnapshot.model_validate(row) for row in rows]


class LeadersPeriod(str, Enum):
    today = "today"
    d7 = "7d"
    d30 = "30d"
    d90 = "90d"
    y1 = "1y"


_PERIOD_DAYS: dict[LeadersPeriod, int] = {
    LeadersPeriod.d7: 7,
    LeadersPeriod.d30: 30,
    LeadersPeriod.d90: 90,
    LeadersPeriod.y1: 365,
}


def _today_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _max_by(entries: list[MarketMoverEntry], key) -> MarketMoverEntry | None:
    candidates = [e for e in entries if key(e) is not None]
    return max(candidates, key=key) if candidates else None


def _min_by(entries: list[MarketMoverEntry], key) -> MarketMoverEntry | None:
    candidates = [e for e in entries if key(e) is not None]
    return min(candidates, key=key) if candidates else None


@router.get(
    "/market-leaders",
    response_model=MarketLeadersResponse,
    summary="Gainer/loser rankings and highlight stats for a period",
    description=(
        "Ranks tracked coins by price movement over the requested period, using only the first "
        "and last real observation loaded inside that period (never estimated); coins with fewer "
        "than 2 observations in the period are excluded entirely. 'today' is backed by "
        "dw.fact_market_intraday (analytics.market_intraday) and only includes coins that have had "
        "intraday data loaded (see etl/ingest_intraday_market_data.py) -- for every other coin it is "
        "genuinely empty, not estimated. The other periods are backed by the daily "
        "analytics.market_history. The summary block (total tracked coins, latest warehouse "
        "update, today's best/worst performer, average movement) always reflects 'today', "
        "regardless of the requested `period`. `coverage` reports how many coins actually "
        "qualified and the real earliest/latest observation in range, plus an `empty_reason` "
        "distinguishing 'no history loaded for this range' from 'history loaded but nothing "
        "qualified' when gainers/losers come back empty."
    ),
)
def get_market_leaders(
    conn: DbDep,
    period: Annotated[LeadersPeriod, Query(description="Ranking window.")] = LeadersPeriod.d7,
    limit: Annotated[
        int, Query(ge=1, le=50, description="Maximum entries in gainers/losers, each.")
    ] = 5,
) -> MarketLeadersResponse:
    now = datetime.now(timezone.utc)
    today_start = _today_start(now)

    if period is LeadersPeriod.today:
        rows = repo.fetch_intraday_movers(conn, today_start, now)
        period_start, period_end = today_start, now
        today_entries = [MarketMoverEntry.model_validate(row) for row in rows]
        entries = today_entries

        earliest_obs, latest_obs = repo.fetch_intraday_observation_range(conn, today_start, now)
    else:
        from_date = now.date() - timedelta(days=_PERIOD_DAYS[period])
        rows = repo.fetch_daily_movers(conn, from_date, None)
        period_start = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
        period_end = now
        entries = [MarketMoverEntry.model_validate(row) for row in rows]

        today_rows = repo.fetch_intraday_movers(conn, today_start, now)
        today_entries = [MarketMoverEntry.model_validate(row) for row in today_rows]

        earliest_date, latest_date = repo.fetch_daily_observation_range(conn, from_date, None)
        earliest_obs = (
            datetime.combine(earliest_date, datetime.min.time(), tzinfo=timezone.utc)
            if earliest_date is not None
            else None
        )
        latest_obs = (
            datetime.combine(latest_date, datetime.min.time(), tzinfo=timezone.utc)
            if latest_date is not None
            else None
        )

    changed = [e for e in entries if e.percent_change is not None]
    gainers = sorted(changed, key=lambda e: e.percent_change, reverse=True)[:limit]
    losers = sorted(changed, key=lambda e: e.percent_change)[:limit]

    highest_volume = _max_by(entries, lambda e: e.volume_24h_usd)
    highest_ranked = _min_by(entries, lambda e: e.market_cap_rank)
    most_volatile = _max_by(entries, lambda e: e.volatility_percent)

    today_movements = [e.percent_change for e in today_entries if e.percent_change is not None]
    summary = MarketLeadersSummary(
        total_tracked_coins=repo.fetch_coin_count(conn),
        latest_update_at=repo.fetch_latest_update_at(conn),
        today_best_performer=_max_by(today_entries, lambda e: e.percent_change),
        today_worst_performer=_min_by(today_entries, lambda e: e.percent_change),
        average_market_movement_percent=(
            sum(today_movements) / len(today_movements) if today_movements else None
        ),
    )

    qualifying_coin_count = len(entries)
    if qualifying_coin_count > 0:
        empty_reason = None
    elif earliest_obs is None:
        empty_reason = (
            "No intraday observations loaded yet today."
            if period is LeadersPeriod.today
            else "Daily history has not been loaded for this period."
        )
    else:
        empty_reason = "No coins have at least two valid observations in this range."

    coverage = MarketLeadersCoverage(
        qualifying_coin_count=qualifying_coin_count,
        earliest_observation=earliest_obs,
        latest_observation=latest_obs,
        empty_reason=empty_reason,
    )

    return MarketLeadersResponse(
        period=period.value,
        period_start=period_start,
        period_end=period_end,
        gainers=gainers,
        losers=losers,
        highest_volume=highest_volume,
        highest_ranked=highest_ranked,
        most_volatile=most_volatile,
        summary=summary,
        coverage=coverage,
    )
