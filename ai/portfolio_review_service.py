import json
from dataclasses import dataclass

from psycopg import Connection
from pydantic import ValidationError

from paper_trading import service as paper_trading_service
from ai.json_utils import strip_ai_json_code_fence
from ai.models import (
    ConcentrationRisk,
    PortfolioAIInsights,
    PortfolioAllocationEntry,
    PortfolioDeterministicMetrics,
    PortfolioHealth,
    PortfolioHealthLevel,
    PortfolioPosition,
    PortfolioReviewSummary,
)
from ai.prompt_builder import build_portfolio_analysis
from ai.provider import AIGenerationResult, AIProvider
from utils.logging_config import get_logger

"""Orchestrates the AI Portfolio Review feature: compute every total, percentage, and health
classification deterministically in this module from the user's existing simulated paper-trading
account (see paper_trading_service.get_portfolio -- the same data the Portfolio page's Paper
Trading tab already displays), then hand a lean summary of that already-computed data to the
active AI provider for interpretation only (see ai_prompt_builder.build_portfolio_analysis). The
model never decides diversification, concentration risk, or the overall health level -- it only
writes five short bullet sections about data it's given, and even that degrades to a fully
deterministic fallback if its response can't be parsed. Never queries CoinGecko or any other
external source, and never recommends buying/selling/holding anything -- this is educational
portfolio analytics, not financial advice.
"""

logger = get_logger("ai.portfolio_review")

TOP_POSITIONS_LIMIT = 5

# Concentration risk: the largest single holding's share of total equity. A coarse, three-level
# categorical badge for display -- see classify_portfolio_health below for the finer-grained
# combination (with diversification_score) that drives the overall health level.
CONCENTRATION_LOW_MAX = 20.0
CONCENTRATION_MEDIUM_MAX = 40.0

# Portfolio Health: the *worse* (higher-risk) of two independent ordinal signals -- concentration
# (largest position's share of total equity) and diversification (spread across holdings, via
# compute_diversification_score) -- the same "combine two independent signals, disagreement/worse
# wins" pattern ai_market_summary_service.determine_market_direction already uses for market
# direction. Each signal is mapped onto the same six-level scale (best to worst); the final level
# is whichever signal reads worse, so a portfolio can't be called "Excellent" on diversification
# alone while sitting 80% in one coin, or vice versa.
_HEALTH_LEVELS: list[PortfolioHealthLevel] = [
    "excellent",
    "good",
    "balanced",
    "concentrated",
    "high_risk",
    "very_high_risk",
]

# (exclusive upper bound on largest_position_percent, level index), ordered best to worst.
# >= the last bound (70%) reads as the worst level (very_high_risk, index 5).
_CONCENTRATION_LEVEL_BOUNDS: list[tuple[float, int]] = [
    (10.0, 0),  # excellent: largest holding under 10% of total equity
    (20.0, 1),  # good: under 20%
    (35.0, 2),  # balanced: under 35%
    (50.0, 3),  # concentrated: under 50%
    (70.0, 4),  # high_risk: under 70%
]

# (inclusive lower bound on diversification_score 0-10, level index), ordered best to worst.
# Below the last bound (score 1) reads as the worst level (very_high_risk, index 5).
_DIVERSIFICATION_LEVEL_BOUNDS: list[tuple[int, int]] = [
    (9, 0),  # excellent
    (7, 1),  # good
    (5, 2),  # balanced
    (3, 3),  # concentrated
    (1, 4),  # high_risk
]


def _level_from_largest_position(largest_position_percent: float) -> int:
    for bound, level in _CONCENTRATION_LEVEL_BOUNDS:
        if largest_position_percent < bound:
            return level
    return 5


def _level_from_diversification(diversification_score: int) -> int:
    for bound, level in _DIVERSIFICATION_LEVEL_BOUNDS:
        if diversification_score >= bound:
            return level
    return 5


def classify_concentration_risk(largest_position_percent: float | None) -> ConcentrationRisk:
    """Coarse three-level concentration badge from the largest holding's share of total equity.
    "unknown" only when there are no priced holdings to compute a share from (all-cash portfolio,
    or every held coin has dropped out of the tracked warehouse set)."""
    if largest_position_percent is None:
        return "unknown"
    if largest_position_percent < CONCENTRATION_LOW_MAX:
        return "low"
    if largest_position_percent <= CONCENTRATION_MEDIUM_MAX:
        return "medium"
    return "high"


def compute_diversification_score(positions: list[dict]) -> int:
    """0 (all value in a single holding) to 10 (many evenly-sized holdings), from the
    Herfindahl-Hirschman Index (HHI) of each priced position's share of total holdings value (cash
    excluded -- diversification measures spread *within* what's invested, not how much is
    invested at all; cash_allocation_percent is the separate signal for that).

    HHI = sum((position_value / total_holdings_value)^2), ranging from 1/n (perfectly even across
    n holdings) up to 1 (all value in one holding). score = round(10 * (1 - HHI)), so a single
    holding always scores 0 and an increasingly even spread across more holdings approaches 10.
    """
    valued = [p for p in positions if p.get("current_value")]
    total = sum(p["current_value"] for p in valued)
    if not valued or total <= 0:
        return 0
    hhi = sum((p["current_value"] / total) ** 2 for p in valued)
    return round(10 * (1 - hhi))


def classify_portfolio_health(
    diversification_score: int, largest_position_percent: float | None, number_of_positions: int
) -> PortfolioHealthLevel:
    """The headline classification: worse of the concentration-derived and diversification-derived
    levels (see the module docstring above `_HEALTH_LEVELS`). An empty, all-cash portfolio is
    "balanced" as a special case -- it carries no concentration risk to measure, but sitting
    entirely in cash isn't "excellent" investing either."""
    if number_of_positions == 0:
        return "balanced"

    concentration_level = _level_from_largest_position(largest_position_percent or 0.0)
    diversification_level = _level_from_diversification(diversification_score)
    return _HEALTH_LEVELS[max(concentration_level, diversification_level)]


@dataclass
class GatheredPortfolioData:
    """Every deterministic figure the Portfolio Review card needs, computed with no AI
    involvement."""

    portfolio_summary: PortfolioReviewSummary
    portfolio_health: PortfolioHealth
    deterministic_metrics: PortfolioDeterministicMetrics
    allocation: list[PortfolioAllocationEntry]
    top_positions: list[PortfolioPosition]


@dataclass
class PortfolioReviewResult:
    gathered: GatheredPortfolioData
    ai_insights: PortfolioAIInsights
    provider: str
    model: str
    response_time_ms: float


# ---------------------------------------------------------------------------
# Deterministic analytics -- no AI involvement below this point except where noted
# ---------------------------------------------------------------------------


def _as_float(value) -> float | None:
    return float(value) if value is not None else None


def gather_portfolio_data(conn: Connection) -> GatheredPortfolioData:
    """Assemble every deterministic figure the Portfolio Review card needs, entirely from
    paper_trading_service.get_portfolio (the same valuation the Portfolio page's Paper Trading tab
    already displays -- holdings priced from analytics.current_market_live, never CoinGecko
    directly). No new SQL and no new repository functions, per the "reuse existing analytics"
    requirement. An empty portfolio (no holdings, only cash) is not an error -- every
    position-dependent metric degrades to `None`/empty rather than being estimated.
    """
    portfolio = paper_trading_service.get_portfolio(conn)

    total_equity = _as_float(portfolio["total_equity"]) or 0.0
    cash_balance = _as_float(portfolio["cash_balance"]) or 0.0
    cash_allocation_percent = (cash_balance / total_equity * 100) if total_equity > 0 else 0.0

    positions = [
        {
            "coin_symbol": h["coin_symbol"],
            "coin_name": h["coin_name"],
            "image_url": h["image_url"],
            "price_change_percentage_24h": _as_float(h["price_change_percentage_24h"]),
            "current_price": _as_float(h["current_price"]),
            "current_value": _as_float(h["current_value"]),
            "unrealized_percent": _as_float(h["unrealized_percent"]),
            "allocation_percent": _as_float(h["allocation_percent"]),
        }
        for h in portfolio["holdings"]
    ]
    number_of_positions = len(positions)
    diversification_score = compute_diversification_score(positions)

    by_allocation = sorted(
        (p for p in positions if p["allocation_percent"] is not None),
        key=lambda p: p["allocation_percent"],
        reverse=True,
    )
    largest = by_allocation[0] if by_allocation else None
    smallest = by_allocation[-1] if by_allocation else None
    largest_position_percent = largest["allocation_percent"] if largest else None

    with_percent = [p for p in positions if p["unrealized_percent"] is not None]
    top_winner = max(with_percent, key=lambda p: p["unrealized_percent"]) if with_percent else None
    top_loser = min(with_percent, key=lambda p: p["unrealized_percent"]) if with_percent else None

    concentration_risk = classify_concentration_risk(largest_position_percent)
    health_level = classify_portfolio_health(diversification_score, largest_position_percent, number_of_positions)

    portfolio_summary = PortfolioReviewSummary(
        total_equity=total_equity,
        cash_balance=cash_balance,
        invested_value=_as_float(portfolio["invested_value"]) or 0.0,
        holdings_value=_as_float(portfolio["holdings_value"]) or 0.0,
        realized_profit=_as_float(portfolio["realized_profit"]) or 0.0,
        unrealized_profit=_as_float(portfolio["unrealized_profit"]) or 0.0,
        total_return_percent=_as_float(portfolio["total_return_percent"]),
        number_of_positions=number_of_positions,
    )

    portfolio_health = PortfolioHealth(
        level=health_level,
        diversification_score=diversification_score,
        concentration_risk=concentration_risk,
        cash_allocation_percent=cash_allocation_percent,
        largest_holding_symbol=largest["coin_symbol"] if largest else None,
        largest_holding_percent=largest_position_percent,
    )

    deterministic_metrics = PortfolioDeterministicMetrics(
        diversification_score=diversification_score,
        concentration_risk=concentration_risk,
        cash_allocation_percent=cash_allocation_percent,
        largest_position_symbol=largest["coin_symbol"] if largest else None,
        largest_position_percent=largest_position_percent,
        smallest_position_symbol=smallest["coin_symbol"] if smallest else None,
        smallest_position_percent=smallest["allocation_percent"] if smallest else None,
        top_winner_symbol=top_winner["coin_symbol"] if top_winner else None,
        top_winner_percent=top_winner["unrealized_percent"] if top_winner else None,
        top_loser_symbol=top_loser["coin_symbol"] if top_loser else None,
        top_loser_percent=top_loser["unrealized_percent"] if top_loser else None,
        number_of_positions=number_of_positions,
    )

    allocation = [
        PortfolioAllocationEntry(label=p["coin_symbol"], percent=p["allocation_percent"], value=p["current_value"])
        for p in by_allocation
    ]
    allocation.append(PortfolioAllocationEntry(label="CASH", percent=cash_allocation_percent, value=cash_balance))

    top_positions = [
        PortfolioPosition(
            coin_symbol=p["coin_symbol"],
            coin_name=p["coin_name"],
            image_url=p["image_url"],
            allocation_percent=p["allocation_percent"],
            current_value=p["current_value"],
            current_price=p["current_price"],
            price_change_percentage_24h=p["price_change_percentage_24h"],
            unrealized_percent=p["unrealized_percent"],
        )
        for p in by_allocation[:TOP_POSITIONS_LIMIT]
    ]

    return GatheredPortfolioData(
        portfolio_summary=portfolio_summary,
        portfolio_health=portfolio_health,
        deterministic_metrics=deterministic_metrics,
        allocation=allocation,
        top_positions=top_positions,
    )


# ---------------------------------------------------------------------------
# AI insights -- the only part of this feature the model actually influences
# ---------------------------------------------------------------------------


def _prompt_payload(gathered: GatheredPortfolioData) -> dict:
    """Reduce GatheredPortfolioData to exactly what the model needs to interpret -- every figure
    and classification in it is already final; the model is never asked to compute or
    re-classify anything itself."""
    summary = gathered.portfolio_summary
    health = gathered.portfolio_health
    metrics = gathered.deterministic_metrics
    return {
        "portfolio_summary": {
            "total_equity_usd": summary.total_equity,
            "cash_balance_usd": summary.cash_balance,
            "invested_value_usd": summary.invested_value,
            "holdings_value_usd": summary.holdings_value,
            "realized_profit_usd": summary.realized_profit,
            "unrealized_profit_usd": summary.unrealized_profit,
            "total_return_percent": summary.total_return_percent,
            "number_of_positions": summary.number_of_positions,
        },
        "portfolio_health": {
            "level": health.level,
            "diversification_score_0_to_10": health.diversification_score,
            "concentration_risk": health.concentration_risk,
            "cash_allocation_percent": health.cash_allocation_percent,
        },
        "deterministic_metrics": {
            "largest_position_symbol": metrics.largest_position_symbol,
            "largest_position_percent": metrics.largest_position_percent,
            "smallest_position_symbol": metrics.smallest_position_symbol,
            "smallest_position_percent": metrics.smallest_position_percent,
            "top_winner_symbol": metrics.top_winner_symbol,
            "top_winner_percent": metrics.top_winner_percent,
            "top_loser_symbol": metrics.top_loser_symbol,
            "top_loser_percent": metrics.top_loser_percent,
        },
        "top_positions": [
            {
                "symbol": p.coin_symbol,
                "allocation_percent": p.allocation_percent,
                "current_value_usd": p.current_value,
                "change_24h_percent": p.price_change_percentage_24h,
                "unrealized_percent": p.unrealized_percent,
            }
            for p in gathered.top_positions
        ],
    }


def parse_portfolio_insights(raw_text: str) -> PortfolioAIInsights:
    """Parse+validate the model's JSON response into PortfolioAIInsights, truncating each array to
    at most 3 items even if the model over-produced. Raises ValueError/pydantic.ValidationError on
    anything that isn't valid JSON matching the expected shape -- callers should catch that and
    fall back to _fallback_portfolio_insights rather than fail the whole request."""
    data = json.loads(strip_ai_json_code_fence(raw_text))
    insights = PortfolioAIInsights.model_validate(data)
    return PortfolioAIInsights(
        strengths=insights.strengths[:3],
        weaknesses=insights.weaknesses[:3],
        interesting_observations=insights.interesting_observations[:3],
        risk_factors=insights.risk_factors[:3],
        educational_notes=insights.educational_notes[:3],
    )


_HEALTH_LABEL: dict[str, str] = {
    "excellent": "excellent",
    "good": "good",
    "balanced": "balanced",
    "concentrated": "concentrated",
    "high_risk": "high risk",
    "very_high_risk": "very high risk",
}


def _fallback_portfolio_insights(gathered: GatheredPortfolioData) -> PortfolioAIInsights:
    """Fully deterministic stand-in for the AI-written insights, used when the model's response
    can't be parsed/validated -- keeps the rest of the (already-deterministic) card intact instead
    of failing the whole request over an LLM formatting slip."""
    summary = gathered.portfolio_summary
    health = gathered.portfolio_health
    metrics = gathered.deterministic_metrics

    strengths = []
    if health.diversification_score >= 6:
        strengths.append(f"Diversification score is {health.diversification_score}/10 across {summary.number_of_positions} positions.")
    if health.concentration_risk == "low":
        strengths.append("No single holding dominates the portfolio's allocation.")

    weaknesses = []
    if health.concentration_risk in ("medium", "high") and metrics.largest_position_symbol:
        weaknesses.append(
            f"{metrics.largest_position_symbol} makes up {metrics.largest_position_percent:.1f}% of total equity."
        )
    if health.diversification_score <= 3:
        weaknesses.append("Value is concentrated in very few positions.")

    interesting_observations = [f"Overall portfolio health reads as {_HEALTH_LABEL[health.level]}."]
    if metrics.top_winner_symbol and metrics.top_winner_percent is not None:
        interesting_observations.append(f"{metrics.top_winner_symbol} is the top performer at {metrics.top_winner_percent:+.2f}%.")

    risk_factors = [
        "AI-generated commentary is temporarily unavailable; the figures above are calculated "
        "directly from the paper-trading account.",
        "This is educational portfolio analytics, not financial advice.",
    ]

    educational_notes = [
        "Diversification score reflects how evenly value is spread across held positions, not "
        "whether any individual position is a good or bad choice.",
        "Concentration risk describes exposure to a single position's price moves, independent of "
        "that position's own performance.",
    ]

    return PortfolioAIInsights(
        strengths=strengths[:3],
        weaknesses=weaknesses[:3],
        interesting_observations=interesting_observations[:3],
        risk_factors=risk_factors[:3],
        educational_notes=educational_notes[:3],
    )


def generate_portfolio_review(conn: Connection, provider: AIProvider) -> PortfolioReviewResult:
    """Gather deterministic paper-trading portfolio data, then ask the AI provider to interpret it
    into five short bullet sections. Provider-level failures (unreachable/timeout/bad model) still
    propagate as AIProviderError, unchanged -- callers map those to HTTP errors. Only a
    successfully-received-but-unparseable AI response degrades gracefully to a deterministic
    fallback, since every other part of the response is already computed with no AI involved.
    """
    gathered = gather_portfolio_data(conn)
    prompt = build_portfolio_analysis(_prompt_payload(gathered))
    generation: AIGenerationResult = provider.generate(prompt.system_prompt, prompt.user_prompt)

    try:
        ai_insights = parse_portfolio_insights(generation.text)
    except (ValueError, ValidationError) as exc:
        logger.warning("AI portfolio insights response could not be parsed (%s); using a deterministic fallback", exc)
        ai_insights = _fallback_portfolio_insights(gathered)

    return PortfolioReviewResult(
        gathered=gathered,
        ai_insights=ai_insights,
        provider=generation.provider,
        model=generation.model,
        response_time_ms=generation.response_time_ms,
    )
