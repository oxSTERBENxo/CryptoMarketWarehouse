import json
from dataclasses import dataclass

from psycopg import Connection
from pydantic import ValidationError

from analytics import repository as repo
from utils import metrics
from ai.json_utils import strip_ai_json_code_fence
from ai.models import (
    CoinAIInsights,
    CoinDeterministicMetrics,
    CoinInformation,
    LiquidityLevel,
    MarketCapTier,
    PriceTrend,
    VolatilityLevel,
    VolumeTrend,
)
from ai.prompt_builder import build_coin_analysis
from ai.provider import AIGenerationResult, AIProvider
from utils.logging_config import get_logger

"""Orchestrates the AI Coin Analysis feature: compute every trend, level, tier, and figure
deterministically in this module from data already in the warehouse, then hand a lean summary of
that already-computed data to the active AI provider for interpretation only (see
ai_prompt_builder.build_coin_analysis). The model never decides a coin's trend, volatility,
liquidity, or market-cap tier -- it only writes five short bullet sections about data it's given,
and even that degrades to a fully deterministic fallback if its response can't be parsed. Never
queries CoinGecko or any other external source -- everything comes from analytics_repository,
reusing the same live current-market data and historical views the rest of the app already uses.
"""

logger = get_logger("ai.coin_analysis")

# Trend: full-history percent change past these thresholds reads as a real directional move rather
# than noise; anything in between is "neutral". A fixed, transparent threshold, not a scored formula.
TREND_BULLISH_THRESHOLD = 2.0
TREND_BEARISH_THRESHOLD = -2.0

# Volatility: (period high - period low) / period low * 100, the same high/low-range formula
# analytics_repository's mover queries already use for volatility_percent.
VOLATILITY_LOW_MAX = 5.0
VOLATILITY_MEDIUM_MAX = 20.0

# Liquidity: 24h volume as a percentage of market cap.
LIQUIDITY_LOW_MAX = 1.0
LIQUIDITY_MEDIUM_MAX = 10.0

# Market-cap tiers, in USD.
LARGE_CAP_MIN = 10_000_000_000.0
MID_CAP_MIN = 1_000_000_000.0
SMALL_CAP_MIN = 50_000_000.0

# Volume trend: today's 24h volume vs. the coin's own average daily volume across its loaded
# history. Above/below these ratios reads as a real shift rather than ordinary day-to-day noise.
VOLUME_TREND_RISING_RATIO = 1.2
VOLUME_TREND_FALLING_RATIO = 0.8


class UnknownCoinError(Exception):
    """Raised when coin_symbol has no current live warehouse snapshot."""

    def __init__(self, coin_symbol: str) -> None:
        super().__init__(f"Unknown coin symbol: {coin_symbol!r}")
        self.coin_symbol = coin_symbol


@dataclass
class GatheredCoinData:
    """Every deterministic figure the Coin Analysis card needs, computed with no AI involvement."""

    coin_information: CoinInformation
    deterministic_metrics: CoinDeterministicMetrics


@dataclass
class CoinAnalysisResult:
    gathered: GatheredCoinData
    ai_insights: CoinAIInsights
    provider: str
    model: str
    response_time_ms: float


# ---------------------------------------------------------------------------
# Deterministic analytics -- no AI involvement below this point except where noted
# ---------------------------------------------------------------------------


def classify_trend(percent_change: float | None) -> PriceTrend:
    """Classify the coin's trend over its tracked history: a real (positive/negative) move beyond
    the fixed thresholds reads as bullish/bearish, anything smaller as neutral. "unknown" only when
    there isn't enough history to compute a percent change at all."""
    if percent_change is None:
        return "unknown"
    if percent_change > TREND_BULLISH_THRESHOLD:
        return "bullish"
    if percent_change < TREND_BEARISH_THRESHOLD:
        return "bearish"
    return "neutral"


def classify_volatility(volatility_percent: float | None) -> VolatilityLevel:
    """Classify volatility from the period high/low range as a percentage of the period low."""
    if volatility_percent is None:
        return "unknown"
    if volatility_percent < VOLATILITY_LOW_MAX:
        return "low"
    if volatility_percent <= VOLATILITY_MEDIUM_MAX:
        return "medium"
    return "high"


def classify_liquidity(liquidity_ratio_percent: float | None) -> LiquidityLevel:
    """Classify liquidity from 24h volume as a percentage of market cap -- a coin trading a large
    share of its own market cap every day is more liquid than one trading a sliver of it."""
    if liquidity_ratio_percent is None:
        return "unknown"
    if liquidity_ratio_percent < LIQUIDITY_LOW_MAX:
        return "low"
    if liquidity_ratio_percent <= LIQUIDITY_MEDIUM_MAX:
        return "medium"
    return "high"


def classify_market_tier(market_cap: float | None) -> MarketCapTier:
    """Classify market-cap tier using fixed USD thresholds."""
    if market_cap is None:
        return "unknown"
    if market_cap >= LARGE_CAP_MIN:
        return "large_cap"
    if market_cap >= MID_CAP_MIN:
        return "mid_cap"
    if market_cap >= SMALL_CAP_MIN:
        return "small_cap"
    return "micro_cap"


def classify_volume_trend(current_volume: float | None, average_volume: float | None) -> VolumeTrend:
    """Classify today's 24h volume against the coin's own average daily volume across its loaded
    history -- "unknown" when either figure is missing or the average is zero (a ratio against a
    zero baseline is meaningless, not "falling")."""
    if current_volume is None or not average_volume:
        return "unknown"
    ratio = current_volume / average_volume
    if ratio >= VOLUME_TREND_RISING_RATIO:
        return "rising"
    if ratio <= VOLUME_TREND_FALLING_RATIO:
        return "falling"
    return "stable"


def _average_volume(history_rows: list[dict]) -> float | None:
    volumes = [r["volume_24h_usd"] for r in history_rows if r.get("volume_24h_usd") is not None]
    return sum(volumes) / len(volumes) if volumes else None


def _average_daily_movement(history_rows: list[dict]) -> float | None:
    """Average absolute day-over-day percent change across the coin's loaded daily history.
    Requires at least 2 observations (a change can't be computed from a single point) and skips any
    pair whose starting price is zero (a percent change against zero is undefined, not 0% or 100%).
    `history_rows` must already be sorted chronologically (ascending)."""
    if len(history_rows) < 2:
        return None

    movements = []
    for previous, current in zip(history_rows, history_rows[1:]):
        change = metrics.percent_change(previous["price_usd"], current["price_usd"])
        if change is not None:
            movements.append(abs(change))

    return sum(movements) / len(movements) if movements else None


def _distance_percent(price: float, reference: float | None) -> float | None:
    return metrics.percent_change(reference, price)


def gather_coin_data(conn: Connection, coin_symbol: str) -> GatheredCoinData:
    """Assemble every deterministic figure the Coin Analysis card needs, entirely from
    analytics_repository -- the live current-market snapshot (current price, 24h change, market
    cap, volume, rank, circulating supply) plus the coin's full loaded daily history (trend,
    volatility, average daily movement, distance from period high/low, volume trend). No new SQL,
    per the "reuse existing analytics" requirement.

    Raises UnknownCoinError if the symbol has no current live warehouse snapshot. A known symbol
    with no historical rows yet (freshly tracked) is not an error -- every history-dependent metric
    simply reports "unknown" instead of being estimated.
    """
    live_prices = repo.fetch_live_prices_for_symbols(conn, [coin_symbol])
    live = live_prices.get(coin_symbol.upper())
    if live is None:
        raise UnknownCoinError(coin_symbol)

    history_summary = repo.fetch_history_summary(conn, coin_symbol, from_date=None, to_date=None)
    history_rows = repo.fetch_history(conn, coin_symbol, from_date=None, to_date=None, order="asc", limit=None)

    price = live["price_usd"]
    market_cap = live.get("market_cap_usd")
    volume_24h = live.get("volume_24h_usd")

    trend_percent_change = history_summary["percent_change"] if history_summary else None
    period_high = history_summary["max_price"] if history_summary else None
    period_low = history_summary["min_price"] if history_summary else None

    volatility_percent = metrics.safe_percent(
        period_high - period_low if period_high is not None and period_low is not None else None,
        period_low,
    )
    liquidity_ratio_percent = metrics.safe_percent(volume_24h, market_cap)
    average_volume = _average_volume(history_rows)

    coin_information = CoinInformation(
        coin_id=live["coin_id"],
        symbol=live["symbol"],
        name=live["name"],
        image_url=live.get("image_url"),
        price=price,
        change_24h=live.get("price_change_percentage_24h"),
        market_cap=market_cap,
        market_cap_rank=live.get("market_cap_rank"),
        volume_24h=volume_24h,
        circulating_supply=live.get("circulating_supply"),
        history_observation_count=history_summary["observation_count"] if history_summary else 0,
        history_start_date=history_summary["period_start_date"] if history_summary else None,
        history_end_date=history_summary["period_end_date"] if history_summary else None,
    )

    deterministic_metrics = CoinDeterministicMetrics(
        price_trend=classify_trend(trend_percent_change),
        trend_percent_change=trend_percent_change,
        momentum_24h_percent=live.get("price_change_percentage_24h"),
        volatility_level=classify_volatility(volatility_percent),
        volatility_percent=volatility_percent,
        liquidity_level=classify_liquidity(liquidity_ratio_percent),
        liquidity_ratio_percent=liquidity_ratio_percent,
        market_cap_tier=classify_market_tier(market_cap),
        volume_trend=classify_volume_trend(volume_24h, average_volume),
        average_daily_movement_percent=_average_daily_movement(history_rows),
        period_high=period_high,
        period_low=period_low,
        distance_from_high_percent=_distance_percent(price, period_high),
        distance_from_low_percent=_distance_percent(price, period_low),
    )

    return GatheredCoinData(coin_information=coin_information, deterministic_metrics=deterministic_metrics)


# ---------------------------------------------------------------------------
# AI insights -- the only part of this feature the model actually influences
# ---------------------------------------------------------------------------


def _prompt_payload(gathered: GatheredCoinData) -> dict:
    """Reduce GatheredCoinData to exactly what the model needs to interpret -- every figure and
    classification in it is already final; the model is never asked to compute or re-classify
    anything itself. Drops fields (coin_id, image_url) that don't help interpretation."""
    info = gathered.coin_information
    metrics = gathered.deterministic_metrics
    return {
        "coin": {
            "name": info.name,
            "symbol": info.symbol.upper(),
            "price_usd": info.price,
            "change_24h_percent": info.change_24h,
            "market_cap_usd": info.market_cap,
            "market_cap_rank": info.market_cap_rank,
            "volume_24h_usd": info.volume_24h,
            "circulating_supply": info.circulating_supply,
            "history_observation_count": info.history_observation_count,
            "history_start_date": info.history_start_date,
            "history_end_date": info.history_end_date,
        },
        "deterministic_metrics": {
            "price_trend": metrics.price_trend,
            "trend_percent_change_over_history": metrics.trend_percent_change,
            "momentum_24h_percent": metrics.momentum_24h_percent,
            "volatility_level": metrics.volatility_level,
            "volatility_percent": metrics.volatility_percent,
            "liquidity_level": metrics.liquidity_level,
            "liquidity_ratio_percent": metrics.liquidity_ratio_percent,
            "market_cap_tier": metrics.market_cap_tier,
            "volume_trend": metrics.volume_trend,
            "average_daily_movement_percent": metrics.average_daily_movement_percent,
            "period_high": metrics.period_high,
            "period_low": metrics.period_low,
            "distance_from_high_percent": metrics.distance_from_high_percent,
            "distance_from_low_percent": metrics.distance_from_low_percent,
        },
    }


def parse_coin_insights(raw_text: str) -> CoinAIInsights:
    """Parse+validate the model's JSON response into CoinAIInsights, truncating each array to at
    most 3 items even if the model over-produced. Raises ValueError/pydantic.ValidationError on
    anything that isn't valid JSON matching the expected shape -- callers should catch that and
    fall back to _fallback_coin_insights rather than fail the whole request."""
    data = json.loads(strip_ai_json_code_fence(raw_text))
    insights = CoinAIInsights.model_validate(data)
    return CoinAIInsights(
        overview=insights.overview[:3],
        performance=insights.performance[:3],
        market_position=insights.market_position[:3],
        things_to_watch=insights.things_to_watch[:3],
        risk=insights.risk[:3],
    )


_TREND_LABEL: dict[str, str] = {
    "bullish": "trending upward",
    "bearish": "trending downward",
    "neutral": "holding roughly steady",
    "unknown": "showing no clear trend (not enough history yet)",
}


def _fallback_coin_insights(gathered: GatheredCoinData) -> CoinAIInsights:
    """Fully deterministic stand-in for the AI-written insights, used when the model's response
    can't be parsed/validated -- keeps the rest of the (already-deterministic) card intact instead
    of failing the whole request over an LLM formatting slip."""
    info = gathered.coin_information
    metrics = gathered.deterministic_metrics

    overview = [f"{info.name} ({info.symbol.upper()}) is currently {_TREND_LABEL[metrics.price_trend]}."]

    performance = []
    if metrics.momentum_24h_percent is not None:
        performance.append(f"24h change is {metrics.momentum_24h_percent:+.2f}%.")
    if metrics.volatility_level != "unknown":
        performance.append(f"Volatility over the tracked period is {metrics.volatility_level}.")

    market_position = []
    if info.market_cap_rank is not None:
        market_position.append(f"Ranked #{info.market_cap_rank} by market capitalization ({metrics.market_cap_tier}).")
    if metrics.liquidity_level != "unknown":
        market_position.append(f"Liquidity (24h volume vs. market cap) is {metrics.liquidity_level}.")

    things_to_watch = []
    if metrics.distance_from_high_percent is not None:
        things_to_watch.append(f"Currently {abs(metrics.distance_from_high_percent):.1f}% below its tracked period high.")
    if metrics.volume_trend != "unknown":
        things_to_watch.append(f"24h trading volume is {metrics.volume_trend} relative to its own average.")

    risk = [
        "AI-generated commentary is temporarily unavailable; the figures above are calculated "
        "directly from warehouse data.",
        "This is educational market analytics, not financial advice.",
    ]

    return CoinAIInsights(
        overview=overview[:3],
        performance=performance[:3],
        market_position=market_position[:3],
        things_to_watch=things_to_watch[:3],
        risk=risk[:3],
    )


def generate_coin_analysis(conn: Connection, provider: AIProvider, coin_symbol: str) -> CoinAnalysisResult:
    """Gather deterministic warehouse data for one coin, then ask the AI provider to interpret it
    into five short bullet sections. Provider-level failures (unreachable/timeout/bad model) still
    propagate as AIProviderError, unchanged -- callers map those to HTTP errors. Only a
    successfully-received-but-unparseable AI response degrades gracefully to a deterministic
    fallback, since every other part of the response is already computed with no AI involved.
    """
    gathered = gather_coin_data(conn, coin_symbol)
    prompt = build_coin_analysis(coin_symbol, _prompt_payload(gathered))
    generation: AIGenerationResult = provider.generate(prompt.system_prompt, prompt.user_prompt)

    try:
        ai_insights = parse_coin_insights(generation.text)
    except (ValueError, ValidationError) as exc:
        logger.warning("AI coin insights response could not be parsed (%s); using a deterministic fallback", exc)
        ai_insights = _fallback_coin_insights(gathered)

    return CoinAnalysisResult(
        gathered=gathered,
        ai_insights=ai_insights,
        provider=generation.provider,
        model=generation.model,
        response_time_ms=generation.response_time_ms,
    )
