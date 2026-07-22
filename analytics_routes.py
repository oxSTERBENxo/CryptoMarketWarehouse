from datetime import date
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

import analytics_repository as repo
from analytics_models import CoinSnapshot, MarketOverview, TopMarketCapEntry, TopVolumeEntry
from database import get_connection

router = APIRouter(prefix="/analytics", tags=["analytics"])


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


def _get_db():
    """Yield a connection for one request; convert any connection/query failure into a 503."""
    try:
        with get_connection() as conn:
            yield conn
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


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
