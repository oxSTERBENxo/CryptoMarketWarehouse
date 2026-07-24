import json
from dataclasses import dataclass

from psycopg import Connection
from pydantic import ValidationError

from analytics import repository as repo
from ai.models import AIInsights, AttentionCoin, MarketCoinEntry, MarketDirection, MarketMetrics, MarketStatus
from ai.json_utils import strip_ai_json_code_fence
from ai.prompt_builder import build_market_summary
from ai.provider import AIGenerationResult, AIProvider
from utils.logging_config import get_logger

"""Orchestrates the AI Market Summary feature: compute every number, ranking, and category
deterministically in this module, then hand a lean summary of that already-computed data to the
active AI provider for interpretation only (see ai_prompt_builder.build_market_summary). The model
never decides which coins rank where, what the overall market direction is, or what any total is
-- it only writes three short bullet sections about data it's given, and even that degrades to a
fully deterministic fallback if its response can't be parsed. Never queries CoinGecko or any other
external source -- everything comes from analytics_repository, reusing the same live
current-market data (analytics.current_market_live) the main dashboard already displays.
"""

logger = get_logger("ai.market_summary")

TOP_N = 5
ATTENTION_LIMIT_PER_CATEGORY = 3
# 24h volume at or above 50% of a coin's own market cap is atypically intense trading -- a
# transparent, fixed threshold rather than a scored/weighted formula.
UNUSUAL_VOLUME_TO_MARKET_CAP_RATIO = 0.5


class NoMarketDataError(Exception):
    """Raised when the warehouse has no ingested market data yet to summarize."""


@dataclass
class GatheredMarketData:
    """Every deterministic figure the AI Market Summary card needs, computed with no AI
    involvement at all."""

    market_status: MarketStatus
    metrics: MarketMetrics
    attention_coins: list[AttentionCoin]
    top_gainers: list[MarketCoinEntry]
    top_losers: list[MarketCoinEntry]
    most_active: list[MarketCoinEntry]


@dataclass
class MarketSummaryResult:
    gathered: GatheredMarketData
    ai_insights: AIInsights
    provider: str
    model: str
    response_time_ms: float


# ---------------------------------------------------------------------------
# Deterministic analytics -- no AI involvement below this point except where noted
# ---------------------------------------------------------------------------


def determine_market_direction(
    average_change_24h: float | None, gainers_count: int, losers_count: int
) -> MarketDirection:
    """Combine two independent signals -- the average 24h change (magnitude) and which side has
    more coins (breadth) -- into one overall direction.

    Returns "mixed" whenever they disagree: e.g. a handful of large movers pull the average
    positive while most tracked coins are actually declining, or vice versa. That is a real, common
    market pattern, not a corner case to paper over by arbitrarily picking one signal.
    """
    if average_change_24h is None or (gainers_count == 0 and losers_count == 0):
        return "neutral"

    change_sign: MarketDirection = (
        "positive" if average_change_24h > 0 else "negative" if average_change_24h < 0 else "neutral"
    )
    breadth_sign: MarketDirection = (
        "positive" if gainers_count > losers_count else "negative" if losers_count > gainers_count else "neutral"
    )

    return change_sign if change_sign == breadth_sign else "mixed"


def _build_headline(
    direction: MarketDirection,
    gainers_count: int,
    losers_count: int,
    coins_tracked: int,
    average_change_24h: float | None,
) -> str:
    change_text = f"{average_change_24h:+.2f}%" if average_change_24h is not None else "an unavailable amount"

    if direction == "negative":
        return (
            f"Market conditions are broadly negative, with {losers_count} of {coins_tracked} tracked "
            f"assets declining and an average 24-hour change of {change_text}."
        )
    if direction == "positive":
        return (
            f"Market conditions are broadly positive, with {gainers_count} of {coins_tracked} tracked "
            f"assets advancing and an average 24-hour change of {change_text}."
        )
    if direction == "mixed":
        return (
            f"Market conditions are mixed, with {gainers_count} of {coins_tracked} tracked assets "
            f"advancing and {losers_count} declining, and an average 24-hour change of {change_text}."
        )
    return f"Market conditions are neutral, with little overall movement across {coins_tracked} tracked assets."


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _movers(coins: list[dict], positive: bool, limit: int) -> list[dict]:
    """The `limit` coins with the strongest actual 24h increase (`positive=True`) or decrease
    (`positive=False`), strictly on the correct side of zero. Ranking by magnitude alone without
    this sign filter would let a merely-less-bad decliner get mislabeled a "top gainer" in a
    broadly red market (or vice versa in a broadly green one)."""
    candidates = [
        c
        for c in coins
        if c.get("price_change_percentage_24h") is not None
        and (c["price_change_percentage_24h"] > 0 if positive else c["price_change_percentage_24h"] < 0)
    ]
    candidates.sort(key=lambda c: c["price_change_percentage_24h"], reverse=positive)
    return candidates[:limit]


def _positive_momentum_coins(coins: list[dict]) -> list[dict]:
    """Strongest Positive Momentum: a real (positive) 24h price gain *and* 24h trading volume at or
    above the tracked median -- filters out thin, illiquid pumps that moved on almost no actual
    trading. Never includes a coin whose 24h change is zero, negative, or unknown."""
    volumes = [c["volume_24h_usd"] for c in coins if c.get("volume_24h_usd") is not None]
    median_volume = _median(volumes)
    if median_volume is None:
        return []

    candidates = [
        c
        for c in coins
        if c.get("price_change_percentage_24h") is not None
        and c["price_change_percentage_24h"] > 0
        and c.get("volume_24h_usd") is not None
        and c["volume_24h_usd"] >= median_volume
    ]
    candidates.sort(key=lambda c: c["price_change_percentage_24h"], reverse=True)
    return candidates[:ATTENTION_LIMIT_PER_CATEGORY]


def _most_active_coins(coins: list[dict], limit: int) -> list[dict]:
    """Most Actively Traded: highest 24h trading volume, full stop. Excludes coins with unknown or
    exactly zero volume -- "most active" cannot describe a coin with no recorded trading. Shared by
    both the top-level `most_active` list (limit=TOP_N) and the "most_active" attention category
    (limit=ATTENTION_LIMIT_PER_CATEGORY) so "what counts as active" has exactly one definition."""
    candidates = [c for c in coins if c.get("volume_24h_usd") is not None and c["volume_24h_usd"] > 0]
    candidates.sort(key=lambda c: c["volume_24h_usd"], reverse=True)
    return candidates[:limit]


def _unusual_activity_coins(coins: list[dict]) -> list[dict]:
    """Unusual Activity: 24h volume large relative to the coin's own market cap -- a signal of
    atypical trading intensity, independent of price direction. Requires both figures to be known
    and market cap to be positive (a ratio against a zero/unknown market cap is meaningless, not
    "unusual")."""
    candidates = [
        c
        for c in coins
        if c.get("volume_24h_usd") is not None
        and c.get("market_cap_usd")
        and c["volume_24h_usd"] / c["market_cap_usd"] >= UNUSUAL_VOLUME_TO_MARKET_CAP_RATIO
    ]
    candidates.sort(key=lambda c: c["volume_24h_usd"] / c["market_cap_usd"], reverse=True)
    return candidates[:ATTENTION_LIMIT_PER_CATEGORY]


def _to_entry(c: dict, total_volume_24h: float | None) -> MarketCoinEntry:
    volume = c.get("volume_24h_usd")
    share = (
        volume / total_volume_24h * 100
        if volume is not None and total_volume_24h is not None and total_volume_24h > 0
        else None
    )
    return MarketCoinEntry(
        coin_id=c["coin_id"],
        name=c["name"],
        symbol=c["symbol"],
        image_url=c.get("image_url"),
        price=c["price_usd"],
        change_24h=c.get("price_change_percentage_24h"),
        volume_24h=volume,
        market_cap=c.get("market_cap_usd"),
        market_cap_rank=c.get("market_cap_rank"),
        volume_share_percent=share,
    )


def _build_attention_coins(coins: list[dict], total_volume_24h: float | None) -> list[AttentionCoin]:
    attention: list[AttentionCoin] = []

    for c in _positive_momentum_coins(coins):
        entry = _to_entry(c, total_volume_24h)
        attention.append(
            AttentionCoin(
                **entry.model_dump(),
                category="positive_momentum",
                reason=f"Positive 24h price movement ({entry.change_24h:+.2f}%) with above-median trading volume.",
            )
        )

    for c in _most_active_coins(coins, ATTENTION_LIMIT_PER_CATEGORY):
        entry = _to_entry(c, total_volume_24h)
        attention.append(
            AttentionCoin(
                **entry.model_dump(),
                category="most_active",
                reason="Highest 24h trading volume among tracked coins.",
            )
        )

    for c in _unusual_activity_coins(coins):
        entry = _to_entry(c, total_volume_24h)
        ratio_percent = c["volume_24h_usd"] / c["market_cap_usd"] * 100
        attention.append(
            AttentionCoin(
                **entry.model_dump(),
                category="unusual_activity",
                reason=f"24h volume equals {ratio_percent:.0f}% of market capitalization, well above typical levels.",
            )
        )

    return attention


def gather_market_data(conn: Connection) -> GatheredMarketData:
    """Assemble every deterministic figure the card needs, entirely from
    analytics_repository.fetch_current_market (the same live snapshot the dashboard's "Current
    Market" view uses) -- no new queries, per the "reuse existing analytics" requirement.

    Raises NoMarketDataError if nothing has been ingested yet.
    """
    result = repo.fetch_current_market(conn, limit=None, order="desc")
    if result is None:
        raise NoMarketDataError("No market data has been ingested yet.")

    coins = result["coins"]
    total_volume_24h = result["total_volume_24h_usd"]

    changes = [c["price_change_percentage_24h"] for c in coins if c.get("price_change_percentage_24h") is not None]
    gainers_count = sum(1 for v in changes if v > 0)
    losers_count = sum(1 for v in changes if v < 0)
    unchanged_count = len(coins) - gainers_count - losers_count
    average_change_24h = sum(changes) / len(changes) if changes else None

    direction = determine_market_direction(average_change_24h, gainers_count, losers_count)
    headline = _build_headline(direction, gainers_count, losers_count, len(coins), average_change_24h)

    market_status = MarketStatus(
        direction=direction,
        headline=headline,
        average_change_24h=average_change_24h,
        gainers_count=gainers_count,
        losers_count=losers_count,
        unchanged_count=unchanged_count,
        coins_tracked=len(coins),
        snapshot_time=result["refreshed_at"],
    )
    metrics = MarketMetrics(total_market_cap=result["total_market_cap_usd"], total_volume_24h=total_volume_24h)

    top_gainers = [_to_entry(c, total_volume_24h) for c in _movers(coins, positive=True, limit=TOP_N)]
    top_losers = [_to_entry(c, total_volume_24h) for c in _movers(coins, positive=False, limit=TOP_N)]
    most_active = [_to_entry(c, total_volume_24h) for c in _most_active_coins(coins, TOP_N)]
    attention_coins = _build_attention_coins(coins, total_volume_24h)

    return GatheredMarketData(
        market_status=market_status,
        metrics=metrics,
        attention_coins=attention_coins,
        top_gainers=top_gainers,
        top_losers=top_losers,
        most_active=most_active,
    )


# ---------------------------------------------------------------------------
# AI insights -- the only part of this feature the model actually influences
# ---------------------------------------------------------------------------


def _entry_for_prompt(entry: MarketCoinEntry) -> dict:
    """Lean, LLM-facing view of a coin entry -- drops fields (image_url, coin_id, market_cap_rank)
    that don't help the model interpret the data and would just add tokens/latency."""
    return {
        "name": entry.name,
        "symbol": entry.symbol.upper(),
        "price": entry.price,
        "change_24h_percent": entry.change_24h,
        "volume_24h_usd": entry.volume_24h,
        "market_cap_usd": entry.market_cap,
    }


def _prompt_payload(gathered: GatheredMarketData) -> dict:
    """Reduce GatheredMarketData to exactly what the model needs to interpret -- every number in
    it is already final; the model is never asked to compute or re-rank anything."""
    status = gathered.market_status
    return {
        "market_status": {
            "direction": status.direction,
            "average_change_24h_percent": status.average_change_24h,
            "gainers_count": status.gainers_count,
            "losers_count": status.losers_count,
            "unchanged_count": status.unchanged_count,
            "coins_tracked": status.coins_tracked,
        },
        "metrics": {
            "total_market_cap_usd": gathered.metrics.total_market_cap,
            "total_volume_24h_usd": gathered.metrics.total_volume_24h,
        },
        "top_gainers": [_entry_for_prompt(e) for e in gathered.top_gainers],
        "top_losers": [_entry_for_prompt(e) for e in gathered.top_losers],
        "most_active": [_entry_for_prompt(e) for e in gathered.most_active],
        "attention_coins": [
            {**_entry_for_prompt(e), "category": e.category, "reason": e.reason} for e in gathered.attention_coins
        ],
    }


def parse_ai_insights(raw_text: str) -> AIInsights:
    """Parse+validate the model's JSON response into AIInsights, truncating each array to at most
    3 items even if the model over-produced. Raises ValueError/pydantic.ValidationError on
    anything that isn't valid JSON matching the expected shape -- callers should catch that and
    fall back to _fallback_ai_insights rather than fail the whole request."""
    data = json.loads(strip_ai_json_code_fence(raw_text))
    insights = AIInsights.model_validate(data)
    return AIInsights(
        market_overview=insights.market_overview[:3],
        what_stands_out=insights.what_stands_out[:3],
        risk_and_caution=insights.risk_and_caution[:3],
    )


def _fallback_ai_insights(gathered: GatheredMarketData) -> AIInsights:
    """Fully deterministic stand-in for the AI-written insights, used when the model's response
    can't be parsed/validated -- keeps the rest of the (already-deterministic) card intact instead
    of failing the whole request over an LLM formatting slip."""
    status = gathered.market_status
    market_overview = [
        f"{status.gainers_count} of {status.coins_tracked} tracked coins are up over 24h, "
        f"{status.losers_count} are down."
    ]
    if status.average_change_24h is not None:
        market_overview.append(f"Average 24h change across tracked coins is {status.average_change_24h:+.2f}%.")

    what_stands_out = []
    if gathered.top_gainers:
        g = gathered.top_gainers[0]
        what_stands_out.append(f"{g.name} ({g.symbol.upper()}) leads gainers at {g.change_24h:+.2f}%.")
    if gathered.top_losers:
        loser = gathered.top_losers[0]
        what_stands_out.append(f"{loser.name} ({loser.symbol.upper()}) leads losers at {loser.change_24h:+.2f}%.")
    if gathered.most_active:
        active = gathered.most_active[0]
        what_stands_out.append(f"{active.name} ({active.symbol.upper()}) has the highest 24h trading volume.")

    risk_and_caution = [
        "AI-generated commentary is temporarily unavailable; the figures above are calculated "
        "directly from warehouse data.",
        "This is educational market analytics, not financial advice.",
    ]

    return AIInsights(
        market_overview=market_overview[:3],
        what_stands_out=what_stands_out[:3],
        risk_and_caution=risk_and_caution[:3],
    )


def generate_market_summary(conn: Connection, provider: AIProvider) -> MarketSummaryResult:
    """Gather deterministic warehouse data, then ask the AI provider to interpret it into three
    short bullet sections. Provider-level failures (unreachable/timeout/bad model) still propagate
    as AIProviderError, unchanged from before -- callers map those to HTTP errors. Only a
    successfully-received-but-unparseable AI response degrades gracefully to a deterministic
    fallback, since every other part of the response is already computed with no AI involved.
    """
    gathered = gather_market_data(conn)
    prompt = build_market_summary(_prompt_payload(gathered))
    generation: AIGenerationResult = provider.generate(prompt.system_prompt, prompt.user_prompt)

    try:
        ai_insights = parse_ai_insights(generation.text)
    except (ValueError, ValidationError) as exc:
        logger.warning("AI insights response could not be parsed (%s); using a deterministic fallback", exc)
        ai_insights = _fallback_ai_insights(gathered)

    return MarketSummaryResult(
        gathered=gathered,
        ai_insights=ai_insights,
        provider=generation.provider,
        model=generation.model,
        response_time_ms=generation.response_time_ms,
    )
