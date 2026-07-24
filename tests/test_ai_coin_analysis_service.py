import pytest

from ai import coin_analysis_service as service
from analytics import repository as analytics_repository
from ai.models import CoinAIInsights
from ai.prompt_builder import PromptPair
from ai.provider import AIGenerationResult


def _live_coin(**overrides) -> dict:
    coin = {
        "coin_id": "bitcoin",
        "symbol": "BTC",
        "name": "Bitcoin",
        "image_url": None,
        "price_usd": 65000.0,
        "price_change_percentage_24h": 2.5,
        "market_cap_usd": 1_300_000_000_000.0,
        "volume_24h_usd": 29_000_000_000.0,
        "circulating_supply": 19_000_000.0,
        "market_cap_rank": 1,
    }
    coin.update(overrides)
    return coin


def _history_row(**overrides) -> dict:
    row = {
        "coin_id": "bitcoin",
        "symbol": "BTC",
        "name": "Bitcoin",
        "image_url": None,
        "snapshot_date": "2026-07-20",
        "price_usd": 60000.0,
        "market_cap_usd": 1_200_000_000_000.0,
        "volume_24h_usd": 25_000_000_000.0,
        "circulating_supply": 19_000_000.0,
        "market_cap_rank": 1,
    }
    row.update(overrides)
    return row


def _history_summary(**overrides) -> dict:
    summary = {
        "coin_id": "bitcoin",
        "symbol": "BTC",
        "name": "Bitcoin",
        "period_start_date": "2026-06-24",
        "period_end_date": "2026-07-24",
        "period_start_price": 60000.0,
        "period_end_price": 65000.0,
        "absolute_change": 5000.0,
        "percent_change": 8.33,
        "min_price": 58000.0,
        "max_price": 66000.0,
        "avg_price": 62000.0,
        "observation_count": 30,
    }
    summary.update(overrides)
    return summary


def _patch_repo(monkeypatch, live=None, history_summary=None, history_rows=None):
    monkeypatch.setattr(
        analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: live if live is not None else {}
    )
    monkeypatch.setattr(
        analytics_repository, "fetch_history_summary", lambda conn, coin_symbol, from_date, to_date: history_summary
    )
    monkeypatch.setattr(
        analytics_repository,
        "fetch_history",
        lambda conn, coin_symbol, from_date, to_date, order, limit: history_rows or [],
    )


# ---------------------------------------------------------------------------
# classify_trend
# ---------------------------------------------------------------------------


def test_classify_trend_bullish_above_threshold():
    assert service.classify_trend(5.0) == "bullish"


def test_classify_trend_bearish_below_threshold():
    assert service.classify_trend(-5.0) == "bearish"


def test_classify_trend_neutral_within_band():
    assert service.classify_trend(1.0) == "neutral"
    assert service.classify_trend(-1.0) == "neutral"


def test_classify_trend_boundary_values_are_neutral():
    assert service.classify_trend(2.0) == "neutral"
    assert service.classify_trend(-2.0) == "neutral"


def test_classify_trend_unknown_when_no_data():
    assert service.classify_trend(None) == "unknown"


# ---------------------------------------------------------------------------
# classify_volatility
# ---------------------------------------------------------------------------


def test_classify_volatility_low():
    assert service.classify_volatility(2.0) == "low"


def test_classify_volatility_medium():
    assert service.classify_volatility(10.0) == "medium"


def test_classify_volatility_high():
    assert service.classify_volatility(25.0) == "high"


def test_classify_volatility_boundaries():
    assert service.classify_volatility(5.0) == "medium"
    assert service.classify_volatility(20.0) == "medium"


def test_classify_volatility_unknown_when_no_data():
    assert service.classify_volatility(None) == "unknown"


# ---------------------------------------------------------------------------
# classify_liquidity
# ---------------------------------------------------------------------------


def test_classify_liquidity_low():
    assert service.classify_liquidity(0.5) == "low"


def test_classify_liquidity_medium():
    assert service.classify_liquidity(5.0) == "medium"


def test_classify_liquidity_high():
    assert service.classify_liquidity(15.0) == "high"


def test_classify_liquidity_boundaries():
    assert service.classify_liquidity(1.0) == "medium"
    assert service.classify_liquidity(10.0) == "medium"


def test_classify_liquidity_unknown_when_no_data():
    assert service.classify_liquidity(None) == "unknown"


# ---------------------------------------------------------------------------
# classify_market_tier
# ---------------------------------------------------------------------------


def test_classify_market_tier_large_cap():
    assert service.classify_market_tier(50_000_000_000.0) == "large_cap"


def test_classify_market_tier_mid_cap():
    assert service.classify_market_tier(5_000_000_000.0) == "mid_cap"


def test_classify_market_tier_small_cap():
    assert service.classify_market_tier(100_000_000.0) == "small_cap"


def test_classify_market_tier_micro_cap():
    assert service.classify_market_tier(1_000_000.0) == "micro_cap"


def test_classify_market_tier_boundaries():
    assert service.classify_market_tier(10_000_000_000.0) == "large_cap"
    assert service.classify_market_tier(1_000_000_000.0) == "mid_cap"
    assert service.classify_market_tier(50_000_000.0) == "small_cap"


def test_classify_market_tier_unknown_when_no_data():
    assert service.classify_market_tier(None) == "unknown"


# ---------------------------------------------------------------------------
# classify_volume_trend
# ---------------------------------------------------------------------------


def test_classify_volume_trend_rising():
    assert service.classify_volume_trend(1200.0, 1000.0) == "rising"


def test_classify_volume_trend_falling():
    assert service.classify_volume_trend(700.0, 1000.0) == "falling"


def test_classify_volume_trend_stable():
    assert service.classify_volume_trend(1000.0, 1000.0) == "stable"


def test_classify_volume_trend_unknown_when_data_missing():
    assert service.classify_volume_trend(None, 1000.0) == "unknown"
    assert service.classify_volume_trend(1000.0, None) == "unknown"
    assert service.classify_volume_trend(1000.0, 0.0) == "unknown"


# ---------------------------------------------------------------------------
# _average_daily_movement
# ---------------------------------------------------------------------------


def test_average_daily_movement_computes_mean_absolute_change():
    rows = [
        _history_row(price_usd=100.0),
        _history_row(price_usd=110.0),  # +10%
        _history_row(price_usd=99.0),  # -10%
    ]
    assert service._average_daily_movement(rows) == pytest.approx(10.0)


def test_average_daily_movement_none_with_fewer_than_two_rows():
    assert service._average_daily_movement([]) is None
    assert service._average_daily_movement([_history_row()]) is None


def test_average_daily_movement_skips_zero_price_pairs():
    rows = [_history_row(price_usd=0.0), _history_row(price_usd=50.0)]
    assert service._average_daily_movement(rows) is None


# ---------------------------------------------------------------------------
# gather_coin_data
# ---------------------------------------------------------------------------


def test_gather_coin_data_raises_when_symbol_unknown(monkeypatch):
    _patch_repo(monkeypatch, live={})

    with pytest.raises(service.UnknownCoinError):
        service.gather_coin_data(object(), "ZZZ")


def test_gather_coin_data_assembles_full_metrics(monkeypatch):
    live = {"BTC": _live_coin(price_usd=65000.0, volume_24h_usd=6_600_000.0, market_cap_usd=1_300_000_000_000.0)}
    summary = _history_summary(percent_change=8.33, min_price=58000.0, max_price=66000.0, observation_count=30)
    rows = [
        _history_row(price_usd=60000.0, volume_24h_usd=6_000_000.0),
        _history_row(price_usd=62000.0, volume_24h_usd=6_000_000.0),
    ]
    _patch_repo(monkeypatch, live=live, history_summary=summary, history_rows=rows)

    data = service.gather_coin_data(object(), "btc")

    info = data.coin_information
    metrics = data.deterministic_metrics
    assert info.coin_id == "bitcoin"
    assert info.price == 65000.0
    assert info.history_observation_count == 30
    assert metrics.price_trend == "bullish"
    assert metrics.trend_percent_change == pytest.approx(8.33)
    assert metrics.period_high == 66000.0
    assert metrics.period_low == 58000.0
    assert metrics.distance_from_high_percent == pytest.approx((65000.0 - 66000.0) / 66000.0 * 100)
    assert metrics.distance_from_low_percent == pytest.approx((65000.0 - 58000.0) / 58000.0 * 100)
    assert metrics.volatility_percent == pytest.approx((66000.0 - 58000.0) / 58000.0 * 100)
    assert metrics.liquidity_ratio_percent == pytest.approx(6_600_000.0 / 1_300_000_000_000.0 * 100)
    assert metrics.market_cap_tier == "large_cap"
    # average history volume is 6,000,000; current volume 6,600,000 -> ratio 1.1 -> stable
    assert metrics.volume_trend == "stable"


def test_gather_coin_data_degrades_gracefully_with_no_history(monkeypatch):
    live = {"BTC": _live_coin()}
    _patch_repo(monkeypatch, live=live, history_summary=None, history_rows=[])

    data = service.gather_coin_data(object(), "BTC")

    info = data.coin_information
    metrics = data.deterministic_metrics
    assert info.history_observation_count == 0
    assert info.history_start_date is None
    assert metrics.price_trend == "unknown"
    assert metrics.volatility_level == "unknown"
    assert metrics.volume_trend == "unknown"
    assert metrics.average_daily_movement_percent is None
    assert metrics.distance_from_high_percent is None
    assert metrics.distance_from_low_percent is None
    # liquidity/market-cap tier don't depend on history and must still be computed
    assert metrics.market_cap_tier == "large_cap"
    assert metrics.liquidity_level != "unknown"


# ---------------------------------------------------------------------------
# AI insights: strict JSON validation + malformed-response fallback
# ---------------------------------------------------------------------------


def test_parse_coin_insights_accepts_valid_json():
    raw = (
        '{"overview": ["Steady."], "performance": ["Up slightly."], '
        '"market_position": ["Large cap."], "things_to_watch": ["Volume."], "risk": ["Not advice."]}'
    )

    insights = service.parse_coin_insights(raw)

    assert insights.overview == ["Steady."]
    assert insights.performance == ["Up slightly."]
    assert insights.market_position == ["Large cap."]
    assert insights.things_to_watch == ["Volume."]
    assert insights.risk == ["Not advice."]


def test_parse_coin_insights_strips_code_fences():
    raw = (
        '```json\n{"overview": ["ok"], "performance": [], "market_position": [], '
        '"things_to_watch": [], "risk": []}\n```'
    )

    insights = service.parse_coin_insights(raw)

    assert insights.overview == ["ok"]


def test_parse_coin_insights_truncates_arrays_over_three_items():
    raw = (
        '{"overview": ["a", "b", "c", "d"], "performance": [], "market_position": [], '
        '"things_to_watch": [], "risk": []}'
    )

    insights = service.parse_coin_insights(raw)

    assert insights.overview == ["a", "b", "c"]


def test_parse_coin_insights_raises_on_invalid_json():
    with pytest.raises(ValueError):
        service.parse_coin_insights("not json at all")


def test_parse_coin_insights_raises_on_wrong_shape():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        service.parse_coin_insights('{"overview": "not a list"}')


def test_generate_coin_analysis_falls_back_on_malformed_ai_response(monkeypatch):
    live = {"BTC": _live_coin()}
    _patch_repo(monkeypatch, live=live, history_summary=_history_summary(), history_rows=[_history_row(), _history_row(price_usd=61000.0)])

    class _GarbageProvider:
        def generate(self, system_prompt, user_prompt):
            return AIGenerationResult(text="I am not JSON.", provider="ollama", model="qwen2.5:7b", response_time_ms=10.0)

    result = service.generate_coin_analysis(object(), _GarbageProvider(), "BTC")

    assert isinstance(result.ai_insights, CoinAIInsights)
    assert len(result.ai_insights.overview) > 0
    assert "temporarily unavailable" in result.ai_insights.risk[0]
    assert result.gathered.coin_information.symbol == "BTC"


def test_generate_coin_analysis_uses_parsed_insights_on_valid_response(monkeypatch):
    live = {"BTC": _live_coin()}
    _patch_repo(monkeypatch, live=live, history_summary=_history_summary(), history_rows=[])

    class _GoodProvider:
        def generate(self, system_prompt, user_prompt):
            return AIGenerationResult(
                text=(
                    '{"overview": ["Calm."], "performance": ["Steady."], "market_position": ["Top tier."], '
                    '"things_to_watch": ["Nothing unusual."], "risk": ["Low data."]}'
                ),
                provider="ollama",
                model="qwen2.5:7b",
                response_time_ms=500.0,
            )

    result = service.generate_coin_analysis(object(), _GoodProvider(), "BTC")

    assert result.ai_insights.overview == ["Calm."]
    assert result.provider == "ollama"
    assert result.response_time_ms == 500.0


def test_generate_coin_analysis_raises_unknown_coin_error(monkeypatch):
    _patch_repo(monkeypatch, live={})

    class _UnusedProvider:
        def generate(self, system_prompt, user_prompt):
            raise AssertionError("must not be called for an unknown coin")

    with pytest.raises(service.UnknownCoinError):
        service.generate_coin_analysis(object(), _UnusedProvider(), "ZZZ")


def test_generate_coin_analysis_builds_prompt_from_gathered_data(monkeypatch):
    captured = {}
    live = {"BTC": _live_coin()}
    _patch_repo(monkeypatch, live=live, history_summary=_history_summary(), history_rows=[])

    def _fake_build(coin_symbol, coin_data):
        captured["coin_symbol"] = coin_symbol
        captured["coin_data"] = coin_data
        return PromptPair(system_prompt="SYS", user_prompt="USER")

    monkeypatch.setattr(service, "build_coin_analysis", _fake_build)

    class _FakeProvider:
        def generate(self, system_prompt, user_prompt):
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            return AIGenerationResult(
                text='{"overview": [], "performance": [], "market_position": [], "things_to_watch": [], "risk": []}',
                provider="ollama",
                model="qwen2.5:7b",
                response_time_ms=1.0,
            )

    service.generate_coin_analysis(object(), _FakeProvider(), "BTC")

    assert captured["coin_symbol"] == "BTC"
    assert captured["system_prompt"] == "SYS"
    assert captured["user_prompt"] == "USER"
    assert "coin" in captured["coin_data"]
    assert "deterministic_metrics" in captured["coin_data"]
    # lean prompt payload must not leak internal-only fields
    assert "coin_id" not in captured["coin_data"]["coin"]
    assert "image_url" not in captured["coin_data"]["coin"]
