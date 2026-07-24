import pytest

from ai import market_summary_service as service
from analytics import repository as analytics_repository
from ai.models import AIInsights
from ai.prompt_builder import PromptPair
from ai.provider import AIGenerationResult


def _coin(**overrides) -> dict:
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


def _current_market(coins: list[dict]) -> dict:
    return {
        "refreshed_at": "2026-07-24T12:00:00Z",
        "coin_count": len(coins),
        "total_market_cap_usd": sum(c["market_cap_usd"] or 0 for c in coins),
        "total_volume_24h_usd": sum(c["volume_24h_usd"] or 0 for c in coins),
        "coins": coins,
    }


# ---------------------------------------------------------------------------
# determine_market_direction
# ---------------------------------------------------------------------------


def test_direction_positive_when_change_and_breadth_agree():
    assert service.determine_market_direction(3.0, gainers_count=70, losers_count=20) == "positive"


def test_direction_negative_when_change_and_breadth_agree():
    assert service.determine_market_direction(-3.0, gainers_count=20, losers_count=70) == "negative"


def test_direction_neutral_when_no_change_data():
    assert service.determine_market_direction(None, gainers_count=0, losers_count=0) == "neutral"


def test_direction_neutral_when_no_gainers_or_losers():
    assert service.determine_market_direction(0.0, gainers_count=0, losers_count=0) == "neutral"


def test_direction_mixed_when_average_positive_but_breadth_negative():
    """The real case found during manual testing: a positive average pulled up by a few large
    movers while most tracked coins are actually declining must read as "mixed", not "positive"."""
    assert service.determine_market_direction(2.58, gainers_count=16, losers_count=63) == "mixed"


def test_direction_mixed_when_average_negative_but_breadth_positive():
    assert service.determine_market_direction(-1.0, gainers_count=63, losers_count=16) == "mixed"


# ---------------------------------------------------------------------------
# gather_market_data -- volume share, rankings, attention categories
# ---------------------------------------------------------------------------


def test_gather_market_data_raises_when_nothing_ingested(monkeypatch):
    monkeypatch.setattr(analytics_repository, "fetch_current_market", lambda conn, limit, order: None)

    with pytest.raises(service.NoMarketDataError):
        service.gather_market_data(object())


def test_gather_market_data_computes_volume_share_percent(monkeypatch):
    coins = [
        _coin(symbol="BTC", volume_24h_usd=300.0),
        _coin(symbol="ETH", volume_24h_usd=700.0),
    ]
    monkeypatch.setattr(
        analytics_repository, "fetch_current_market", lambda conn, limit, order: _current_market(coins)
    )

    data = service.gather_market_data(object())

    by_symbol = {e.symbol: e for e in data.most_active}
    assert by_symbol["ETH"].volume_share_percent == pytest.approx(70.0)
    assert by_symbol["BTC"].volume_share_percent == pytest.approx(30.0)


def test_gather_market_data_ranks_gainers_losers_and_most_active(monkeypatch):
    coins = [
        _coin(symbol="BTC", price_change_percentage_24h=5.0, volume_24h_usd=100.0, market_cap_usd=1000.0),
        _coin(symbol="ETH", price_change_percentage_24h=-3.0, volume_24h_usd=300.0, market_cap_usd=500.0),
        _coin(symbol="SOL", price_change_percentage_24h=10.0, volume_24h_usd=50.0, market_cap_usd=2000.0),
        _coin(symbol="ADA", price_change_percentage_24h=-8.0, volume_24h_usd=10.0, market_cap_usd=100.0),
        _coin(symbol="DOGE", price_change_percentage_24h=None, volume_24h_usd=None, market_cap_usd=None),
    ]
    monkeypatch.setattr(
        analytics_repository, "fetch_current_market", lambda conn, limit, order: _current_market(coins)
    )

    data = service.gather_market_data(object())

    assert [c.symbol for c in data.top_gainers] == ["SOL", "BTC"]
    assert [c.symbol for c in data.top_losers] == ["ADA", "ETH"]
    assert [c.symbol for c in data.most_active] == ["ETH", "BTC", "SOL", "ADA"]
    assert data.market_status.gainers_count == 2
    assert data.market_status.losers_count == 2
    assert data.market_status.unchanged_count == 1
    assert data.market_status.coins_tracked == 5


def test_gather_market_data_never_labels_a_decliner_as_a_gainer(monkeypatch):
    """In a broadly red market, the least-bad decliner must not show up in top_gainers just
    because it ranks highest by raw value -- top_gainers must only ever contain real increases."""
    coins = [
        _coin(symbol="BTC", price_change_percentage_24h=-1.0),
        _coin(symbol="ETH", price_change_percentage_24h=-5.0),
        _coin(symbol="SOL", price_change_percentage_24h=-9.0),
    ]
    monkeypatch.setattr(
        analytics_repository, "fetch_current_market", lambda conn, limit, order: _current_market(coins)
    )

    data = service.gather_market_data(object())

    assert data.top_gainers == []
    assert [c.symbol for c in data.top_losers] == ["SOL", "ETH", "BTC"]


def test_gather_market_data_most_active_excludes_zero_volume_coins(monkeypatch):
    coins = [
        _coin(symbol="BTC", volume_24h_usd=0.0),
        _coin(symbol="ETH", volume_24h_usd=None),
        _coin(symbol="SOL", volume_24h_usd=500.0),
    ]
    monkeypatch.setattr(
        analytics_repository, "fetch_current_market", lambda conn, limit, order: _current_market(coins)
    )

    data = service.gather_market_data(object())

    assert [c.symbol for c in data.most_active] == ["SOL"]


# ---------------------------------------------------------------------------
# Attention category selection
# ---------------------------------------------------------------------------


def test_positive_momentum_requires_positive_change_and_above_median_volume():
    # Volume pool for the median: [1000, 1, 2000, 1] -> sorted [1, 1, 1000, 2000] -> median 500.5.
    coins = [
        _coin(symbol="A", price_change_percentage_24h=10.0, volume_24h_usd=1000.0),  # positive, above median
        _coin(symbol="B", price_change_percentage_24h=1.0, volume_24h_usd=1.0),  # positive but below median
        _coin(symbol="C", price_change_percentage_24h=-5.0, volume_24h_usd=2000.0),  # negative, excluded
        _coin(symbol="D", price_change_percentage_24h=None, volume_24h_usd=1.0),  # no change data, excluded
    ]

    result = service._positive_momentum_coins(coins)

    assert [c["symbol"] for c in result] == ["A"]


def test_positive_momentum_never_includes_a_negative_or_zero_change_coin():
    coins = [
        _coin(symbol="A", price_change_percentage_24h=0.0, volume_24h_usd=1000.0),
        _coin(symbol="B", price_change_percentage_24h=-0.01, volume_24h_usd=1000.0),
    ]

    result = service._positive_momentum_coins(coins)

    assert result == []


def test_most_active_coins_excludes_zero_and_none_volume():
    coins = [
        _coin(symbol="A", volume_24h_usd=0.0),
        _coin(symbol="B", volume_24h_usd=None),
        _coin(symbol="C", volume_24h_usd=5.0),
    ]

    result = service._most_active_coins(coins, limit=5)

    assert [c["symbol"] for c in result] == ["C"]


def test_unusual_activity_requires_high_volume_to_market_cap_ratio():
    coins = [
        _coin(symbol="A", volume_24h_usd=600.0, market_cap_usd=1000.0),  # ratio 0.6 -- qualifies
        _coin(symbol="B", volume_24h_usd=100.0, market_cap_usd=1000.0),  # ratio 0.1 -- too low
        _coin(symbol="C", volume_24h_usd=500.0, market_cap_usd=0.0),  # zero market cap -- excluded
        _coin(symbol="D", volume_24h_usd=500.0, market_cap_usd=None),  # unknown market cap -- excluded
    ]

    result = service._unusual_activity_coins(coins)

    assert [c["symbol"] for c in result] == ["A"]


def test_attention_coins_are_capped_per_category(monkeypatch):
    coins = [
        _coin(
            symbol=f"C{i}",
            coin_id=f"coin{i}",
            price_change_percentage_24h=float(i + 1),
            volume_24h_usd=1_000_000.0 + i,
            market_cap_usd=100.0,
        )
        for i in range(5)
    ]
    monkeypatch.setattr(
        analytics_repository, "fetch_current_market", lambda conn, limit, order: _current_market(coins)
    )

    data = service.gather_market_data(object())

    momentum = [c for c in data.attention_coins if c.category == "positive_momentum"]
    most_active = [c for c in data.attention_coins if c.category == "most_active"]
    assert len(momentum) <= service.ATTENTION_LIMIT_PER_CATEGORY
    assert len(most_active) <= service.ATTENTION_LIMIT_PER_CATEGORY


# ---------------------------------------------------------------------------
# AI insights: strict JSON validation + malformed-response fallback
# ---------------------------------------------------------------------------


def test_parse_ai_insights_accepts_valid_json():
    raw = (
        '{"market_overview": ["Market is calm."], '
        '"what_stands_out": ["BTC leads gainers."], '
        '"risk_and_caution": ["Volatility remains high."]}'
    )

    insights = service.parse_ai_insights(raw)

    assert insights.market_overview == ["Market is calm."]
    assert insights.what_stands_out == ["BTC leads gainers."]
    assert insights.risk_and_caution == ["Volatility remains high."]


def test_parse_ai_insights_strips_code_fences():
    raw = '```json\n{"market_overview": ["ok"], "what_stands_out": [], "risk_and_caution": []}\n```'

    insights = service.parse_ai_insights(raw)

    assert insights.market_overview == ["ok"]


def test_parse_ai_insights_truncates_arrays_over_three_items():
    raw = '{"market_overview": ["a", "b", "c", "d"], "what_stands_out": [], "risk_and_caution": []}'

    insights = service.parse_ai_insights(raw)

    assert insights.market_overview == ["a", "b", "c"]


def test_parse_ai_insights_raises_on_invalid_json():
    with pytest.raises(ValueError):
        service.parse_ai_insights("not json at all")


def test_parse_ai_insights_raises_on_wrong_shape():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        service.parse_ai_insights('{"market_overview": "not a list"}')


def test_generate_market_summary_falls_back_on_malformed_ai_response(monkeypatch):
    """A model that returns garbage must not break the request -- the deterministic sections
    (already computed) still come back, backed by a template-generated ai_insights."""
    coins = [
        _coin(symbol="BTC", price_change_percentage_24h=5.0, volume_24h_usd=500.0),
        _coin(symbol="ETH", price_change_percentage_24h=-2.0, volume_24h_usd=300.0),
    ]
    monkeypatch.setattr(
        analytics_repository, "fetch_current_market", lambda conn, limit, order: _current_market(coins)
    )

    class _GarbageProvider:
        def generate(self, system_prompt, user_prompt):
            return AIGenerationResult(text="I am not JSON.", provider="ollama", model="qwen2.5:7b", response_time_ms=10.0)

    result = service.generate_market_summary(object(), _GarbageProvider())

    assert isinstance(result.ai_insights, AIInsights)
    assert len(result.ai_insights.market_overview) > 0
    assert "temporarily unavailable" in result.ai_insights.risk_and_caution[0]
    assert result.gathered.top_gainers[0].symbol == "BTC"


def test_generate_market_summary_uses_parsed_insights_on_valid_response(monkeypatch):
    coins = [_coin()]
    monkeypatch.setattr(
        analytics_repository, "fetch_current_market", lambda conn, limit, order: _current_market(coins)
    )

    class _GoodProvider:
        def generate(self, system_prompt, user_prompt):
            return AIGenerationResult(
                text='{"market_overview": ["Calm."], "what_stands_out": ["BTC steady."], "risk_and_caution": ["Low data."]}',
                provider="ollama",
                model="qwen2.5:7b",
                response_time_ms=500.0,
            )

    result = service.generate_market_summary(object(), _GoodProvider())

    assert result.ai_insights.market_overview == ["Calm."]
    assert result.provider == "ollama"
    assert result.response_time_ms == 500.0


def test_generate_market_summary_builds_prompt_from_gathered_data(monkeypatch):
    captured = {}
    coins = [_coin()]
    monkeypatch.setattr(
        analytics_repository, "fetch_current_market", lambda conn, limit, order: _current_market(coins)
    )

    def _fake_build(market_data):
        captured["market_data"] = market_data
        return PromptPair(system_prompt="SYS", user_prompt="USER")

    monkeypatch.setattr(service, "build_market_summary", _fake_build)

    class _FakeProvider:
        def generate(self, system_prompt, user_prompt):
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            return AIGenerationResult(
                text='{"market_overview": [], "what_stands_out": [], "risk_and_caution": []}',
                provider="ollama",
                model="qwen2.5:7b",
                response_time_ms=1.0,
            )

    service.generate_market_summary(object(), _FakeProvider())

    assert captured["system_prompt"] == "SYS"
    assert captured["user_prompt"] == "USER"
    assert "market_status" in captured["market_data"]
    assert "top_gainers" in captured["market_data"]
    # lean prompt payload must not leak internal-only fields
    assert "coin_id" not in captured["market_data"]["top_gainers"][0] if captured["market_data"]["top_gainers"] else True
