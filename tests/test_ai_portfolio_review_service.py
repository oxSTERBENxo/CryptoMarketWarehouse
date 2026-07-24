import json

import pytest
from pydantic import ValidationError

from ai import portfolio_review_service as service
from paper_trading import service as paper_trading_service
from ai.models import PortfolioAIInsights
from ai.provider import AIGenerationResult, AIProvider


def _holding(**overrides) -> dict:
    holding = {
        "coin_symbol": "BTC",
        "coin_name": "Bitcoin",
        "image_url": None,
        "price_change_percentage_24h": 2.1,
        "quantity": 0.5,
        "average_cost": 60000.0,
        "current_price": 65000.0,
        "current_value": 32500.0,
        "unrealized_profit": 2500.0,
        "unrealized_percent": 8.33,
        "allocation_percent": 35.0,
    }
    holding.update(overrides)
    return holding


def _portfolio(**overrides) -> dict:
    portfolio = {
        "account": {"id": 1, "name": "Paper Trading Account"},
        "holdings": [],
        "cash_balance": 100000.0,
        "invested_value": 0.0,
        "holdings_value": 0.0,
        "total_equity": 100000.0,
        "realized_profit": 0.0,
        "unrealized_profit": 0.0,
        "total_return_percent": 0.0,
        "best_performer": None,
        "worst_performer": None,
    }
    portfolio.update(overrides)
    return portfolio


def _patch_portfolio(monkeypatch, portfolio: dict):
    monkeypatch.setattr(paper_trading_service, "get_portfolio", lambda conn: portfolio)


# ---------------------------------------------------------------------------
# classify_concentration_risk
# ---------------------------------------------------------------------------


def test_classify_concentration_risk_unknown_when_none():
    assert service.classify_concentration_risk(None) == "unknown"


def test_classify_concentration_risk_low_below_threshold():
    assert service.classify_concentration_risk(19.9) == "low"


def test_classify_concentration_risk_medium_at_low_boundary():
    assert service.classify_concentration_risk(20.0) == "medium"


def test_classify_concentration_risk_medium_at_high_boundary():
    assert service.classify_concentration_risk(40.0) == "medium"


def test_classify_concentration_risk_high_above_threshold():
    assert service.classify_concentration_risk(40.1) == "high"


# ---------------------------------------------------------------------------
# compute_diversification_score
# ---------------------------------------------------------------------------


def test_diversification_score_empty_positions_is_zero():
    assert service.compute_diversification_score([]) == 0


def test_diversification_score_single_holding_is_zero():
    assert service.compute_diversification_score([{"current_value": 1000.0}]) == 0


def test_diversification_score_two_even_holdings_is_five():
    positions = [{"current_value": 500.0}, {"current_value": 500.0}]
    assert service.compute_diversification_score(positions) == 5


def test_diversification_score_ten_even_holdings_is_nine():
    positions = [{"current_value": 100.0} for _ in range(10)]
    assert service.compute_diversification_score(positions) == 9


def test_diversification_score_ignores_unpriced_holdings():
    positions = [{"current_value": 1000.0}, {"current_value": None}]
    assert service.compute_diversification_score(positions) == 0


def test_diversification_score_zero_total_value_is_zero():
    positions = [{"current_value": 0.0}, {"current_value": 0.0}]
    assert service.compute_diversification_score(positions) == 0


# ---------------------------------------------------------------------------
# classify_portfolio_health
# ---------------------------------------------------------------------------


def test_portfolio_health_empty_portfolio_is_balanced():
    assert service.classify_portfolio_health(diversification_score=0, largest_position_percent=None, number_of_positions=0) == "balanced"


def test_portfolio_health_excellent_when_both_signals_are_great():
    assert (
        service.classify_portfolio_health(diversification_score=9, largest_position_percent=5.0, number_of_positions=10)
        == "excellent"
    )


def test_portfolio_health_worst_signal_wins_over_good_diversification():
    """A single huge position should never read as excellent just because the diversification
    score (computed elsewhere) happens to be high -- concentration risk dominates."""
    result = service.classify_portfolio_health(diversification_score=9, largest_position_percent=80.0, number_of_positions=2)
    assert result == "very_high_risk"


def test_portfolio_health_worst_signal_wins_over_good_concentration():
    result = service.classify_portfolio_health(diversification_score=0, largest_position_percent=5.0, number_of_positions=5)
    assert result == "very_high_risk"


def test_portfolio_health_none_largest_position_treated_as_zero():
    result = service.classify_portfolio_health(diversification_score=9, largest_position_percent=None, number_of_positions=1)
    assert result == "excellent"


@pytest.mark.parametrize(
    "largest_pct,expected",
    [
        (5.0, "excellent"),
        (15.0, "good"),
        (30.0, "balanced"),
        (45.0, "concentrated"),
        (60.0, "high_risk"),
        (75.0, "very_high_risk"),
    ],
)
def test_portfolio_health_concentration_thresholds(largest_pct, expected):
    # diversification_score fixed at 9 (best) so the concentration signal alone drives the result.
    assert service.classify_portfolio_health(diversification_score=9, largest_position_percent=largest_pct, number_of_positions=3) == expected


# ---------------------------------------------------------------------------
# gather_portfolio_data
# ---------------------------------------------------------------------------


def test_gather_empty_portfolio(monkeypatch):
    _patch_portfolio(monkeypatch, _portfolio())

    gathered = service.gather_portfolio_data(conn=object())

    assert gathered.portfolio_summary.number_of_positions == 0
    assert gathered.portfolio_summary.total_equity == 100000.0
    assert gathered.portfolio_health.level == "balanced"
    assert gathered.portfolio_health.diversification_score == 0
    assert gathered.portfolio_health.concentration_risk == "unknown"
    assert gathered.portfolio_health.largest_holding_symbol is None
    assert gathered.deterministic_metrics.number_of_positions == 0
    assert gathered.top_positions == []
    # cash is the only allocation entry, at 100%
    assert len(gathered.allocation) == 1
    assert gathered.allocation[0].label == "CASH"
    assert gathered.allocation[0].percent == 100.0


def test_gather_multi_holding_portfolio(monkeypatch):
    portfolio = _portfolio(
        holdings=[
            _holding(coin_symbol="BTC", current_value=36750.0, allocation_percent=35.0, unrealized_percent=12.0),
            _holding(coin_symbol="ETH", current_value=15750.0, allocation_percent=15.0, unrealized_percent=-3.0, current_price=3000.0),
        ],
        cash_balance=52500.0,
        invested_value=45000.0,
        holdings_value=52500.0,
        total_equity=105000.0,
        realized_profit=500.0,
        unrealized_profit=7500.0,
        total_return_percent=5.0,
    )
    _patch_portfolio(monkeypatch, portfolio)

    gathered = service.gather_portfolio_data(conn=object())

    assert gathered.portfolio_summary.number_of_positions == 2
    assert gathered.portfolio_health.largest_holding_symbol == "BTC"
    assert gathered.portfolio_health.largest_holding_percent == 35.0
    assert gathered.deterministic_metrics.smallest_position_symbol == "ETH"
    assert gathered.deterministic_metrics.top_winner_symbol == "BTC"
    assert gathered.deterministic_metrics.top_winner_percent == 12.0
    assert gathered.deterministic_metrics.top_loser_symbol == "ETH"
    assert gathered.deterministic_metrics.top_loser_percent == -3.0
    # BTC + ETH + CASH
    assert len(gathered.allocation) == 3
    assert gathered.allocation[0].label == "BTC"  # sorted by allocation percent, descending
    assert gathered.top_positions[0].coin_symbol == "BTC"


def test_gather_caps_top_positions_at_limit(monkeypatch):
    holdings = [
        _holding(coin_symbol=f"COIN{i}", current_value=float(100 - i), allocation_percent=float(100 - i))
        for i in range(8)
    ]
    _patch_portfolio(monkeypatch, _portfolio(holdings=holdings))

    gathered = service.gather_portfolio_data(conn=object())

    assert len(gathered.top_positions) == service.TOP_POSITIONS_LIMIT
    assert gathered.top_positions[0].coin_symbol == "COIN0"


def test_gather_handles_holding_with_no_current_price(monkeypatch):
    """A holding whose coin has dropped out of the tracked warehouse set entirely -- current_value/
    allocation_percent are None; it must not blow up the largest/smallest/winner/loser math."""
    portfolio = _portfolio(
        holdings=[_holding(coin_symbol="ZZZ", current_price=None, current_value=None, unrealized_percent=None, allocation_percent=None)]
    )
    _patch_portfolio(monkeypatch, portfolio)

    gathered = service.gather_portfolio_data(conn=object())

    assert gathered.portfolio_summary.number_of_positions == 1
    assert gathered.portfolio_health.largest_holding_symbol is None
    assert gathered.top_positions == []


# ---------------------------------------------------------------------------
# parse_portfolio_insights / _fallback_portfolio_insights
# ---------------------------------------------------------------------------


def _valid_ai_json() -> str:
    return json.dumps(
        {
            "strengths": ["Well spread across positions."],
            "weaknesses": ["Large cash allocation."],
            "interesting_observations": ["BTC is the top performer."],
            "risk_factors": ["Medium concentration risk."],
            "educational_notes": ["Diversification reduces single-position exposure."],
        }
    )


def test_parse_portfolio_insights_valid_json():
    insights = service.parse_portfolio_insights(_valid_ai_json())

    assert isinstance(insights, PortfolioAIInsights)
    assert insights.strengths == ["Well spread across positions."]


def test_parse_portfolio_insights_truncates_to_three_items():
    data = json.loads(_valid_ai_json())
    data["strengths"] = ["one", "two", "three", "four", "five"]

    insights = service.parse_portfolio_insights(json.dumps(data))

    assert insights.strengths == ["one", "two", "three"]


def test_parse_portfolio_insights_strips_code_fence():
    fenced = f"```json\n{_valid_ai_json()}\n```"

    insights = service.parse_portfolio_insights(fenced)

    assert insights.strengths == ["Well spread across positions."]


def test_parse_portfolio_insights_raises_on_invalid_json():
    with pytest.raises(ValueError):
        service.parse_portfolio_insights("not json at all")


def test_parse_portfolio_insights_raises_on_missing_keys():
    with pytest.raises(ValidationError):
        service.parse_portfolio_insights(json.dumps({"strengths": ["ok"]}))


def test_fallback_portfolio_insights_always_notes_educational_purpose(monkeypatch):
    _patch_portfolio(monkeypatch, _portfolio())
    gathered = service.gather_portfolio_data(conn=object())

    insights = service._fallback_portfolio_insights(gathered)

    assert any("financial advice" in note for note in insights.risk_factors)
    assert len(insights.educational_notes) > 0


# ---------------------------------------------------------------------------
# generate_portfolio_review
# ---------------------------------------------------------------------------


class _StubProvider(AIProvider):
    name = "ollama"

    def __init__(self, text: str):
        self._text = text

    def generate(self, system_prompt, user_prompt):
        return AIGenerationResult(text=self._text, provider="ollama", model="qwen2.5:7b", response_time_ms=100.0)


def test_generate_portfolio_review_uses_parsed_ai_insights(monkeypatch):
    _patch_portfolio(monkeypatch, _portfolio())

    result = service.generate_portfolio_review(conn=object(), provider=_StubProvider(_valid_ai_json()))

    assert result.ai_insights.strengths == ["Well spread across positions."]
    assert result.provider == "ollama"
    assert result.model == "qwen2.5:7b"


def test_generate_portfolio_review_falls_back_on_malformed_ai_response(monkeypatch):
    _patch_portfolio(monkeypatch, _portfolio())

    result = service.generate_portfolio_review(conn=object(), provider=_StubProvider("not valid json"))

    assert result.ai_insights.risk_factors  # deterministic fallback still populated
    assert any("financial advice" in note for note in result.ai_insights.risk_factors)
