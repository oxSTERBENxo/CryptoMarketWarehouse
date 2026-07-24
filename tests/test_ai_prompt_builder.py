import pytest

from ai import prompt_builder as pb

_SAMPLE_MARKET_DATA = {
    "market_status": {
        "direction": "mixed",
        "average_change_24h_percent": 2.58,
        "gainers_count": 16,
        "losers_count": 63,
        "unchanged_count": 21,
        "coins_tracked": 100,
    },
    "metrics": {"total_market_cap_usd": 2_255_941_544_333.0, "total_volume_24h_usd": 94_859_076_454.78},
    "top_gainers": [{"name": "Solana", "symbol": "SOL", "price": 150.0, "change_24h_percent": 10.0}],
    "top_losers": [{"name": "Cardano", "symbol": "ADA", "price": 0.4, "change_24h_percent": -8.0}],
    "most_active": [{"name": "Tether", "symbol": "USDT", "volume_24h_usd": 4_000_000_000.0}],
    "attention_coins": [
        {"name": "Solana", "symbol": "SOL", "category": "positive_momentum", "reason": "Positive movement with volume."}
    ],
}


def test_build_market_summary_returns_prompt_pair():
    result = pb.build_market_summary(_SAMPLE_MARKET_DATA)

    assert isinstance(result, pb.PromptPair)


def test_build_market_summary_system_prompt_sets_the_ground_rules():
    result = pb.build_market_summary(_SAMPLE_MARKET_DATA)

    assert "ONLY analyze the supplied data" in result.system_prompt
    assert "STRICT JSON ONLY" in result.system_prompt
    assert "not buying pressure" in result.system_prompt
    assert "bought the most" in result.system_prompt
    assert "Never recommend buying, selling, or holding" in result.system_prompt
    assert "not financial advice" in result.system_prompt
    assert "market_overview" in result.system_prompt
    assert "what_stands_out" in result.system_prompt
    assert "risk_and_caution" in result.system_prompt


def test_build_market_summary_never_asks_the_model_to_rank_or_recompute():
    result = pb.build_market_summary(_SAMPLE_MARKET_DATA)

    assert "already computed deterministically" in result.system_prompt
    assert "never recompute or contradict" in result.user_prompt


def test_build_market_summary_user_prompt_embeds_data_separately_from_instructions():
    result = pb.build_market_summary(_SAMPLE_MARKET_DATA)

    assert "=== MARKET DATA (JSON) ===" in result.user_prompt
    assert "=== END MARKET DATA ===" in result.user_prompt
    assert '"symbol": "SOL"' in result.user_prompt
    data_end = result.user_prompt.index("=== END MARKET DATA ===")
    # the final instruction must come after the delimited data, not interleaved with it
    assert result.user_prompt.index("market_overview, what_stands_out") > data_end


def test_build_compare_prompt_not_implemented_yet():
    with pytest.raises(NotImplementedError):
        pb.build_compare_prompt(["BTC", "ETH"], [])


def test_build_market_summary_embeds_non_ascii_coin_names_literally():
    """Non-Latin coin names (e.g. CJK) must appear as real characters, not \\uXXXX escapes --
    otherwise some models echo the escape sequence back literally instead of the actual name."""
    data = dict(_SAMPLE_MARKET_DATA)
    data["top_gainers"] = [{"symbol": "CNY", "name": "币安人生", "price": 1.0}]

    result = pb.build_market_summary(data)

    assert "币安人生" in result.user_prompt
    assert "\\u5e01" not in result.user_prompt


# ---------------------------------------------------------------------------
# build_coin_analysis
# ---------------------------------------------------------------------------

_SAMPLE_COIN_DATA = {
    "coin": {
        "name": "Bitcoin",
        "symbol": "BTC",
        "price_usd": 65000.0,
        "change_24h_percent": 2.5,
        "market_cap_usd": 1_300_000_000_000.0,
        "market_cap_rank": 1,
        "volume_24h_usd": 29_000_000_000.0,
        "circulating_supply": 19_000_000.0,
        "history_observation_count": 30,
        "history_start_date": "2026-06-24",
        "history_end_date": "2026-07-24",
    },
    "deterministic_metrics": {
        "price_trend": "bullish",
        "trend_percent_change_over_history": 8.33,
        "momentum_24h_percent": 2.5,
        "volatility_level": "medium",
        "volatility_percent": 12.0,
        "liquidity_level": "high",
        "liquidity_ratio_percent": 2.2,
        "market_cap_tier": "large_cap",
        "volume_trend": "stable",
        "average_daily_movement_percent": 3.1,
        "period_high": 66000.0,
        "period_low": 58000.0,
        "distance_from_high_percent": -1.5,
        "distance_from_low_percent": 12.1,
    },
}


def test_build_coin_analysis_returns_prompt_pair():
    result = pb.build_coin_analysis("BTC", _SAMPLE_COIN_DATA)

    assert isinstance(result, pb.PromptPair)


def test_build_coin_analysis_system_prompt_sets_the_ground_rules():
    result = pb.build_coin_analysis("BTC", _SAMPLE_COIN_DATA)

    assert "ONLY interpret the supplied data" in result.system_prompt
    assert "STRICT JSON ONLY" in result.system_prompt
    assert "Never invent" in result.system_prompt
    assert "Never speculate about outside events" in result.system_prompt
    assert "Never recommend buying, selling, or holding" in result.system_prompt
    assert "not financial advice" in result.system_prompt
    assert "overview" in result.system_prompt
    assert "performance" in result.system_prompt
    assert "market_position" in result.system_prompt
    assert "things_to_watch" in result.system_prompt
    assert "risk" in result.system_prompt


def test_build_coin_analysis_never_asks_the_model_to_recompute():
    result = pb.build_coin_analysis("BTC", _SAMPLE_COIN_DATA)

    assert "already computed deterministically" in result.system_prompt
    assert "never recompute or contradict" in result.user_prompt


def test_build_coin_analysis_user_prompt_embeds_data_separately_from_instructions():
    result = pb.build_coin_analysis("BTC", _SAMPLE_COIN_DATA)

    assert "=== COIN DATA (JSON) ===" in result.user_prompt
    assert "=== END COIN DATA ===" in result.user_prompt
    assert '"symbol": "BTC"' in result.user_prompt
    data_end = result.user_prompt.index("=== END COIN DATA ===")
    # the final instruction must come after the delimited data, not interleaved with it
    assert result.user_prompt.index("overview, performance") > data_end


def test_build_coin_analysis_embeds_the_requested_symbol():
    result = pb.build_coin_analysis("btc", _SAMPLE_COIN_DATA)

    assert "BTC" in result.user_prompt


def test_build_coin_analysis_embeds_non_ascii_coin_names_literally():
    data = {
        "coin": {"name": "币安人生", "symbol": "CNY"},
        "deterministic_metrics": {},
    }

    result = pb.build_coin_analysis("CNY", data)

    assert "币安人生" in result.user_prompt
    assert "\\u5e01" not in result.user_prompt


# ---------------------------------------------------------------------------
# build_portfolio_analysis
# ---------------------------------------------------------------------------

_SAMPLE_PORTFOLIO_DATA = {
    "portfolio_summary": {
        "total_equity_usd": 105_000.0,
        "cash_balance_usd": 20_000.0,
        "invested_value_usd": 80_000.0,
        "holdings_value_usd": 85_000.0,
        "realized_profit_usd": 500.0,
        "unrealized_profit_usd": 5_000.0,
        "total_return_percent": 5.0,
        "number_of_positions": 3,
    },
    "portfolio_health": {
        "level": "good",
        "diversification_score_0_to_10": 7,
        "concentration_risk": "medium",
        "cash_allocation_percent": 19.05,
    },
    "deterministic_metrics": {
        "largest_position_symbol": "BTC",
        "largest_position_percent": 35.0,
        "smallest_position_symbol": "ADA",
        "smallest_position_percent": 5.0,
        "top_winner_symbol": "BTC",
        "top_winner_percent": 12.0,
        "top_loser_symbol": "ADA",
        "top_loser_percent": -3.0,
    },
    "top_positions": [
        {"symbol": "BTC", "allocation_percent": 35.0, "current_value_usd": 36_750.0, "change_24h_percent": 2.1, "unrealized_percent": 12.0},
    ],
}


def test_build_portfolio_analysis_returns_prompt_pair():
    result = pb.build_portfolio_analysis(_SAMPLE_PORTFOLIO_DATA)

    assert isinstance(result, pb.PromptPair)


def test_build_portfolio_analysis_system_prompt_sets_the_ground_rules():
    result = pb.build_portfolio_analysis(_SAMPLE_PORTFOLIO_DATA)

    assert "ONLY interpret the supplied data" in result.system_prompt
    assert "STRICT JSON ONLY" in result.system_prompt
    assert "Never invent numbers" in result.system_prompt
    assert "Never invent news" in result.system_prompt
    assert "Never speculate" in result.system_prompt
    assert "Never recommend buying, selling, or holding" in result.system_prompt
    assert "not financial advice" in result.system_prompt
    assert "strengths" in result.system_prompt
    assert "weaknesses" in result.system_prompt
    assert "interesting_observations" in result.system_prompt
    assert "risk_factors" in result.system_prompt
    assert "educational_notes" in result.system_prompt


def test_build_portfolio_analysis_never_asks_the_model_to_recompute():
    result = pb.build_portfolio_analysis(_SAMPLE_PORTFOLIO_DATA)

    assert "already computed deterministically" in result.system_prompt
    assert "never recompute or contradict" in result.user_prompt


def test_build_portfolio_analysis_user_prompt_embeds_data_separately_from_instructions():
    result = pb.build_portfolio_analysis(_SAMPLE_PORTFOLIO_DATA)

    assert "=== RAW DATA (JSON) ===" in result.user_prompt
    assert "=== END RAW DATA ===" in result.user_prompt
    assert '"largest_position_symbol": "BTC"' in result.user_prompt
    data_end = result.user_prompt.index("=== END RAW DATA ===")
    # the final instruction must come after the delimited data, not interleaved with it
    assert result.user_prompt.index("strengths, weaknesses") > data_end
