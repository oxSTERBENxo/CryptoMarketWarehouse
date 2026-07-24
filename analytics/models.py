from datetime import date, datetime

from pydantic import BaseModel


class MarketOverview(BaseModel):
    snapshot_date: date
    coin_count: int
    total_market_cap_usd: float | None
    total_volume_24h_usd: float | None


class CoinSnapshot(BaseModel):
    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    snapshot_date: date
    price_usd: float
    market_cap_usd: float | None
    volume_24h_usd: float | None
    circulating_supply: float | None
    market_cap_rank: int | None


class CurrentMarketCoin(BaseModel):
    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    price_usd: float
    price_change_percentage_24h: float | None = None
    market_cap_usd: float | None
    volume_24h_usd: float | None
    circulating_supply: float | None
    market_cap_rank: int | None


class CurrentMarketSnapshot(BaseModel):
    """Live current-market view backing the main dashboard's Take New Snapshot refresh: sourced
    from the most recently ingested staging run (analytics.current_market_live), not the daily
    dw.fact_market_snapshot grain -- see MarketOverview/CoinSnapshot for that."""

    refreshed_at: datetime | None
    coin_count: int
    total_market_cap_usd: float | None
    total_volume_24h_usd: float | None
    coins: list[CurrentMarketCoin]


class TopMarketCapEntry(BaseModel):
    market_cap_position: int
    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    snapshot_date: date
    market_cap_usd: float | None
    price_usd: float


class TopVolumeEntry(BaseModel):
    volume_position: int
    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    snapshot_date: date
    volume_24h_usd: float | None
    price_usd: float


class CoinHistorySummary(BaseModel):
    coin_id: str
    symbol: str
    name: str
    period_start_date: date
    period_end_date: date
    period_start_price: float
    period_end_price: float
    absolute_change: float
    percent_change: float | None
    min_price: float
    max_price: float
    avg_price: float
    observation_count: int


class IntradaySnapshot(BaseModel):
    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    observation_timestamp: datetime
    price_usd: float
    market_cap_usd: float | None
    volume_24h_usd: float | None


class MarketMoverEntry(BaseModel):
    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    start_price: float
    end_price: float
    percent_change: float | None
    high_price: float
    low_price: float
    volatility_percent: float | None
    volume_24h_usd: float | None
    market_cap_usd: float | None
    market_cap_rank: int | None
    observation_count: int


class MarketLeadersSummary(BaseModel):
    total_tracked_coins: int
    latest_update_at: datetime | None
    today_best_performer: MarketMoverEntry | None
    today_worst_performer: MarketMoverEntry | None
    average_market_movement_percent: float | None


class MarketLeadersCoverage(BaseModel):
    """Reports what data actually backs this response, so the frontend can distinguish a
    genuinely quiet period from a broken pipeline instead of showing a bare 'no data'."""

    qualifying_coin_count: int
    earliest_observation: datetime | None
    latest_observation: datetime | None
    empty_reason: str | None


class MarketLeadersResponse(BaseModel):
    period: str
    period_start: datetime | None
    period_end: datetime | None
    gainers: list[MarketMoverEntry]
    losers: list[MarketMoverEntry]
    highest_volume: MarketMoverEntry | None
    highest_ranked: MarketMoverEntry | None
    most_volatile: MarketMoverEntry | None
    summary: MarketLeadersSummary
    coverage: MarketLeadersCoverage
