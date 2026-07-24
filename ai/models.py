from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class AIHealthResponse(BaseModel):
    provider: str
    model: str
    healthy: bool
    response_time_ms: float | None = None
    error: str | None = None


class AIProviderInfo(BaseModel):
    name: str
    active: bool
    configured: bool
    detail: str | None = None


class AIProvidersResponse(BaseModel):
    active_provider: str
    providers: list[AIProviderInfo]


MarketDirection = Literal["positive", "negative", "mixed", "neutral"]
AttentionCategory = Literal["positive_momentum", "most_active", "unusual_activity"]


class MarketStatus(BaseModel):
    direction: MarketDirection
    headline: str
    average_change_24h: float | None
    gainers_count: int
    losers_count: int
    unchanged_count: int
    coins_tracked: int
    snapshot_time: datetime | None


class MarketMetrics(BaseModel):
    total_market_cap: float | None
    total_volume_24h: float | None


class MarketCoinEntry(BaseModel):
    coin_id: str
    name: str
    symbol: str
    image_url: str | None
    price: float
    change_24h: float | None
    volume_24h: float | None
    market_cap: float | None
    market_cap_rank: int | None
    # Only meaningful for entries drawn from a volume-ranked list (most_active/trading activity);
    # left None elsewhere rather than computed against an unrelated total.
    volume_share_percent: float | None = None


class AttentionCoin(MarketCoinEntry):
    category: AttentionCategory
    reason: str


class AIInsights(BaseModel):
    market_overview: list[str]
    what_stands_out: list[str]
    risk_and_caution: list[str]


class MarketSummaryResponse(BaseModel):
    generated_at: datetime
    provider: str
    model: str
    response_time_ms: float
    market_status: MarketStatus
    metrics: MarketMetrics
    attention_coins: list[AttentionCoin]
    top_gainers: list[MarketCoinEntry]
    top_losers: list[MarketCoinEntry]
    most_active: list[MarketCoinEntry]
    ai_insights: AIInsights


# ---------------------------------------------------------------------------
# AI Coin Analysis (POST /ai/coin-analysis/{coin_symbol})
# ---------------------------------------------------------------------------

# "unknown" covers a coin with a live snapshot but not enough historical data to classify --
# a real, honest state (e.g. a coin ingested for the first time today) rather than a guess.
PriceTrend = Literal["bullish", "bearish", "neutral", "unknown"]
VolatilityLevel = Literal["low", "medium", "high", "unknown"]
LiquidityLevel = Literal["low", "medium", "high", "unknown"]
MarketCapTier = Literal["large_cap", "mid_cap", "small_cap", "micro_cap", "unknown"]
VolumeTrend = Literal["rising", "falling", "stable", "unknown"]


class CoinInformation(BaseModel):
    """Every raw warehouse figure the Coin Analysis card needs, sourced from
    analytics_repository (current live snapshot + full history), no AI involvement."""

    coin_id: str
    symbol: str
    name: str
    image_url: str | None
    price: float
    change_24h: float | None
    market_cap: float | None
    market_cap_rank: int | None
    volume_24h: float | None
    circulating_supply: float | None
    history_observation_count: int
    history_start_date: date | None
    history_end_date: date | None


class CoinDeterministicMetrics(BaseModel):
    """Every interpretive figure computed deterministically in ai/coin_analysis_service.py --
    the AI is only ever asked to explain these, never to calculate or override them."""

    price_trend: PriceTrend
    trend_percent_change: float | None
    momentum_24h_percent: float | None
    volatility_level: VolatilityLevel
    volatility_percent: float | None
    liquidity_level: LiquidityLevel
    liquidity_ratio_percent: float | None
    market_cap_tier: MarketCapTier
    volume_trend: VolumeTrend
    average_daily_movement_percent: float | None
    period_high: float | None
    period_low: float | None
    distance_from_high_percent: float | None
    distance_from_low_percent: float | None


class CoinAIInsights(BaseModel):
    """The only AI-authored part of the Coin Analysis response -- five short bullet sections
    interpreting CoinInformation/CoinDeterministicMetrics, at most 3 items each."""

    overview: list[str]
    performance: list[str]
    market_position: list[str]
    things_to_watch: list[str]
    risk: list[str]


class CoinAnalysisResponse(BaseModel):
    generated_at: datetime
    provider: str
    model: str
    response_time_ms: float
    coin_information: CoinInformation
    deterministic_metrics: CoinDeterministicMetrics
    ai_insights: CoinAIInsights


# ---------------------------------------------------------------------------
# AI Portfolio Review (POST /ai/portfolio-review)
# ---------------------------------------------------------------------------

# "unknown" covers an all-cash portfolio (no priced holdings to compute a concentration ratio
# from) -- a real, honest state rather than a guess.
PortfolioHealthLevel = Literal["excellent", "good", "balanced", "concentrated", "high_risk", "very_high_risk"]
ConcentrationRisk = Literal["low", "medium", "high", "unknown"]


class PortfolioReviewSummary(BaseModel):
    """Every raw valuation figure the review needs, sourced from paper_trading_service.get_portfolio
    (the same paper-trading account the Portfolio page's Paper Trading tab already displays), no AI
    involvement."""

    total_equity: float
    cash_balance: float
    invested_value: float
    holdings_value: float
    realized_profit: float
    unrealized_profit: float
    total_return_percent: float | None
    number_of_positions: int


class PortfolioHealth(BaseModel):
    """The headline deterministic classification -- see
    ai_portfolio_review_service.classify_portfolio_health for exactly how `level` is derived from
    diversification_score and concentration_risk."""

    level: PortfolioHealthLevel
    diversification_score: int
    concentration_risk: ConcentrationRisk
    cash_allocation_percent: float
    largest_holding_symbol: str | None
    largest_holding_percent: float | None


class PortfolioDeterministicMetrics(BaseModel):
    """Every interpretive figure computed deterministically in ai/portfolio_review_service.py --
    the AI is only ever asked to explain these, never to calculate or override them."""

    diversification_score: int
    concentration_risk: ConcentrationRisk
    cash_allocation_percent: float
    largest_position_symbol: str | None
    largest_position_percent: float | None
    smallest_position_symbol: str | None
    smallest_position_percent: float | None
    top_winner_symbol: str | None
    top_winner_percent: float | None
    top_loser_symbol: str | None
    top_loser_percent: float | None
    number_of_positions: int


class PortfolioAllocationEntry(BaseModel):
    """One slice of the portfolio's allocation breakdown -- every held coin plus a final "CASH"
    entry, percents summing to ~100% of total_equity."""

    label: str
    percent: float
    value: float


class PortfolioPosition(BaseModel):
    """One holding for the "Top Holdings" cards -- allocation-ranked, capped at
    ai_portfolio_review_service.TOP_POSITIONS_LIMIT."""

    coin_symbol: str
    coin_name: str | None
    image_url: str | None
    allocation_percent: float | None
    current_value: float | None
    current_price: float | None
    price_change_percentage_24h: float | None
    unrealized_percent: float | None


class PortfolioAIInsights(BaseModel):
    """The only AI-authored part of the Portfolio Review response -- five short bullet sections
    interpreting PortfolioReviewSummary/PortfolioHealth/PortfolioDeterministicMetrics, at most 3
    items each. Never a buy/sell recommendation."""

    strengths: list[str]
    weaknesses: list[str]
    interesting_observations: list[str]
    risk_factors: list[str]
    educational_notes: list[str]


class PortfolioReviewResponse(BaseModel):
    generated_at: datetime
    provider: str
    model: str
    response_time_ms: float
    portfolio_summary: PortfolioReviewSummary
    portfolio_health: PortfolioHealth
    deterministic_metrics: PortfolioDeterministicMetrics
    allocation: list[PortfolioAllocationEntry]
    top_positions: list[PortfolioPosition]
    ai_insights: PortfolioAIInsights
