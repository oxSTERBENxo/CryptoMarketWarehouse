"""Request/response models for the Analytics Explorer -- the interactive historical-query
feature. A request pairs a metric with a condition (plus a date range, optional threshold,
optional value filters, sorting, and pagination) and the service resolves that pair to one of the
independently-implemented analyses in analytics_explorer_service.ANALYSES. Everything is computed
deterministically from the warehouse (analytics.market_history); no external APIs and no AI."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class ExplorerMetric(str, Enum):
    price = "price"
    volume = "volume"
    market_cap = "market_cap"
    market_cap_rank = "market_cap_rank"
    volatility = "volatility"


class ExplorerCondition(str, Enum):
    increased_by_percent = "increased_by_percent"
    decreased_by_percent = "decreased_by_percent"
    increased_by_amount = "increased_by_amount"
    decreased_by_amount = "decreased_by_amount"
    improved_by = "improved_by"
    declined_by = "declined_by"
    top_n = "top_n"
    bottom_n = "bottom_n"


class ExplorerSortField(str, Enum):
    percent_change = "percent_change"
    dollar_change = "dollar_change"
    end_price = "end_price"
    avg_volume = "avg_volume"
    rank_change = "rank_change"
    market_cap = "market_cap"
    volatility = "volatility"


class ExplorerSortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class ExplorerFilters(BaseModel):
    """Optional value filters applied before the analysis condition. All bounds are inclusive.
    Price and rank bounds apply to the period-end value; a coin whose end value is unavailable
    (NULL in the warehouse) is excluded by any filter on that value."""

    min_market_cap: float | None = Field(default=None, ge=0)
    max_market_cap: float | None = Field(default=None, ge=0)
    min_avg_volume: float | None = Field(default=None, ge=0)
    min_rank: int | None = Field(default=None, ge=1)
    max_rank: int | None = Field(default=None, ge=1)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)


class ExplorerRequest(BaseModel):
    metric: ExplorerMetric
    condition: ExplorerCondition
    from_date: date
    to_date: date
    # Interpreted per analysis: percent for *_by_percent, dollars for *_by_amount, places for
    # improved_by/declined_by. Ignored by top_n/bottom_n analyses (the result limit is the N).
    threshold: float | None = None
    filters: ExplorerFilters = ExplorerFilters()
    # None means "use the analysis's natural sort" (e.g. percent_change desc for top gainers).
    sort_by: ExplorerSortField | None = None
    sort_order: ExplorerSortOrder = ExplorerSortOrder.desc
    limit: int = Field(default=25, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class ExplorerResultRow(BaseModel):
    """One qualifying coin with the full set of period statistics, so the result table can show
    rich information regardless of which analysis produced it. start/end values come from the
    first/last real observation inside the requested range (never estimated); coins with fewer
    than 2 observations in range never appear."""

    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    start_date: date
    end_date: date
    start_price: float
    end_price: float
    dollar_change: float
    percent_change: float | None
    low_price: float
    high_price: float
    avg_price: float | None
    avg_volume: float | None
    volatility_percent: float | None
    start_rank: int | None
    end_rank: int | None
    # start_rank - end_rank: positive means the coin improved (moved toward #1).
    rank_change: int | None
    market_cap_usd: float | None
    observation_count: int


class ExplorerSummary(BaseModel):
    """Deterministic aggregates over every row that passed the analysis (not just the current
    page), backing the summary cards above the result table."""

    results_found: int
    average_percent_change: float | None
    largest_increase_percent: float | None
    largest_increase_symbol: str | None
    largest_decrease_percent: float | None
    largest_decrease_symbol: str | None
    average_volume: float | None


class ExplorerResponse(BaseModel):
    analysis_label: str
    metric: ExplorerMetric
    condition: ExplorerCondition
    from_date: date
    to_date: date
    threshold: float | None
    sort_by: ExplorerSortField
    sort_order: ExplorerSortOrder
    total_results: int
    offset: int
    limit: int
    summary: ExplorerSummary
    rows: list[ExplorerResultRow]
