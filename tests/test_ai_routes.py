from fastapi.testclient import TestClient

from ai import coin_analysis_service
from ai import market_summary_service
from ai import portfolio_review_service
from ai import routes as ai_routes
from ai.provider import (
    AIGenerationResult,
    AIInvalidResponseError,
    AIModelNotFoundError,
    AIProvider,
    AIProviderUnavailableError,
    AITimeoutError,
)
from main import app

client = TestClient(app)


class _StubProvider(AIProvider):
    name = "ollama"

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def generate(self, system_prompt, user_prompt):
        if self._error is not None:
            raise self._error
        return self._result


def _override(provider: AIProvider):
    app.dependency_overrides[ai_routes._get_provider] = lambda: provider


def _fake_db():
    yield object()


def _override_db():
    app.dependency_overrides[ai_routes._get_db] = _fake_db


def teardown_function():
    app.dependency_overrides.pop(ai_routes._get_provider, None)
    app.dependency_overrides.pop(ai_routes._get_db, None)


def test_health_returns_healthy_when_provider_responds():
    _override(
        _StubProvider(
            result=AIGenerationResult(
                text="ok", provider="ollama", model="qwen3:8b", response_time_ms=42.0
            )
        )
    )

    response = client.get("/ai/health")

    assert response.status_code == 200
    body = response.json()
    assert body["healthy"] is True
    assert body["provider"] == "ollama"
    assert body["model"] == "qwen3:8b"
    assert body["response_time_ms"] == 42.0


def test_health_returns_503_when_provider_unavailable():
    _override(_StubProvider(error=AIProviderUnavailableError("could not reach ollama")))

    response = client.get("/ai/health")

    assert response.status_code == 503
    assert "could not reach ollama" in response.json()["detail"]


def test_health_returns_504_on_timeout():
    _override(_StubProvider(error=AITimeoutError("timed out")))

    response = client.get("/ai/health")

    assert response.status_code == 504


def test_health_returns_502_on_model_not_found():
    _override(_StubProvider(error=AIModelNotFoundError("no such model")))

    response = client.get("/ai/health")

    assert response.status_code == 502


def test_health_returns_502_on_invalid_response():
    _override(_StubProvider(error=AIInvalidResponseError("bad shape")))

    response = client.get("/ai/health")

    assert response.status_code == 502


def test_providers_lists_ollama_as_active_by_default(monkeypatch):
    from ai import config as ai_config

    monkeypatch.setattr(ai_config, "AI_PROVIDER", "ollama")

    response = client.get("/ai/providers")

    assert response.status_code == 200
    body = response.json()
    assert body["active_provider"] == "ollama"
    names = {p["name"]: p for p in body["providers"]}
    assert names["ollama"]["active"] is True
    assert names["ollama"]["configured"] is True
    assert names["groq"]["configured"] is True


def test_providers_lists_groq_as_configured_when_active(monkeypatch):
    from ai import config as ai_config

    monkeypatch.setattr(ai_config, "AI_PROVIDER", "groq")
    monkeypatch.setattr(ai_config, "GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr(ai_config, "GROQ_MODEL", "llama-3.3-70b-versatile")

    response = client.get("/ai/providers")

    assert response.status_code == 200
    body = response.json()
    assert body["active_provider"] == "groq"
    names = {p["name"]: p for p in body["providers"]}
    assert names["groq"]["active"] is True
    assert names["groq"]["configured"] is True
    assert names["groq"]["detail"] == "llama-3.3-70b-versatile (API key set)"


def _sample_gathered():
    from ai.market_summary_service import GatheredMarketData
    from ai.models import MarketMetrics, MarketStatus

    return GatheredMarketData(
        market_status=MarketStatus(
            direction="mixed",
            headline="Market conditions are mixed, with 16 of 100 tracked assets advancing and 63 declining, "
            "and an average 24-hour change of +2.58%.",
            average_change_24h=2.58,
            gainers_count=16,
            losers_count=63,
            unchanged_count=21,
            coins_tracked=100,
            snapshot_time="2026-07-24T12:00:00Z",
        ),
        metrics=MarketMetrics(total_market_cap=2_255_941_544_333.0, total_volume_24h=94_859_076_454.78),
        attention_coins=[],
        top_gainers=[],
        top_losers=[],
        most_active=[],
    )


def test_market_summary_returns_structured_payload_on_success(monkeypatch):
    from ai.market_summary_service import MarketSummaryResult
    from ai.models import AIInsights

    _override_db()
    _override(_StubProvider())  # unused: generate_market_summary is monkeypatched below
    monkeypatch.setattr(
        market_summary_service,
        "generate_market_summary",
        lambda conn, provider: MarketSummaryResult(
            gathered=_sample_gathered(),
            ai_insights=AIInsights(
                market_overview=["Broad decline across tracked coins."],
                what_stands_out=["A handful of large movers pulled the average positive."],
                risk_and_caution=["Breadth remains weak despite the positive average."],
            ),
            provider="ollama",
            model="qwen2.5:7b",
            response_time_ms=1234.5,
        ),
    )

    response = client.post("/ai/market-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert body["model"] == "qwen2.5:7b"
    assert body["response_time_ms"] == 1234.5
    assert body["generated_at"] is not None
    assert body["market_status"]["direction"] == "mixed"
    assert body["market_status"]["gainers_count"] == 16
    assert body["metrics"]["total_market_cap"] == 2_255_941_544_333.0
    assert body["ai_insights"]["market_overview"] == ["Broad decline across tracked coins."]
    assert body["attention_coins"] == []
    assert body["top_gainers"] == []


def test_market_summary_returns_404_when_no_data(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider):
        raise market_summary_service.NoMarketDataError("No market data has been ingested yet.")

    monkeypatch.setattr(market_summary_service, "generate_market_summary", _raise)

    response = client.post("/ai/market-summary")

    assert response.status_code == 404


def test_market_summary_returns_503_when_provider_unavailable(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider):
        raise AIProviderUnavailableError("could not reach ollama")

    monkeypatch.setattr(market_summary_service, "generate_market_summary", _raise)

    response = client.post("/ai/market-summary")

    assert response.status_code == 503


def test_market_summary_returns_504_on_timeout(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider):
        raise AITimeoutError("timed out")

    monkeypatch.setattr(market_summary_service, "generate_market_summary", _raise)

    response = client.post("/ai/market-summary")

    assert response.status_code == 504


def test_market_summary_returns_502_on_invalid_response(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider):
        raise AIInvalidResponseError("bad shape")

    monkeypatch.setattr(market_summary_service, "generate_market_summary", _raise)

    response = client.post("/ai/market-summary")

    assert response.status_code == 502


def _sample_gathered_coin():
    from ai.coin_analysis_service import GatheredCoinData
    from ai.models import CoinDeterministicMetrics, CoinInformation

    return GatheredCoinData(
        coin_information=CoinInformation(
            coin_id="bitcoin",
            symbol="BTC",
            name="Bitcoin",
            image_url=None,
            price=65000.0,
            change_24h=2.5,
            market_cap=1_300_000_000_000.0,
            market_cap_rank=1,
            volume_24h=29_000_000_000.0,
            circulating_supply=19_000_000.0,
            history_observation_count=30,
            history_start_date="2026-06-24",
            history_end_date="2026-07-24",
        ),
        deterministic_metrics=CoinDeterministicMetrics(
            price_trend="bullish",
            trend_percent_change=8.33,
            momentum_24h_percent=2.5,
            volatility_level="medium",
            volatility_percent=12.0,
            liquidity_level="high",
            liquidity_ratio_percent=2.2,
            market_cap_tier="large_cap",
            volume_trend="stable",
            average_daily_movement_percent=3.1,
            period_high=66000.0,
            period_low=58000.0,
            distance_from_high_percent=-1.5,
            distance_from_low_percent=12.1,
        ),
    )


def test_coin_analysis_returns_structured_payload_on_success(monkeypatch):
    from ai.coin_analysis_service import CoinAnalysisResult
    from ai.models import CoinAIInsights

    _override_db()
    _override(_StubProvider())  # unused: generate_coin_analysis is monkeypatched below
    monkeypatch.setattr(
        coin_analysis_service,
        "generate_coin_analysis",
        lambda conn, provider, coin_symbol: CoinAnalysisResult(
            gathered=_sample_gathered_coin(),
            ai_insights=CoinAIInsights(
                overview=["Bitcoin is trending upward."],
                performance=["24h change is +2.50%."],
                market_position=["Ranked #1 by market capitalization."],
                things_to_watch=["Volume is stable."],
                risk=["Educational analytics, not financial advice."],
            ),
            provider="ollama",
            model="qwen2.5:7b",
            response_time_ms=987.6,
        ),
    )

    response = client.post("/ai/coin-analysis/BTC")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert body["model"] == "qwen2.5:7b"
    assert body["response_time_ms"] == 987.6
    assert body["generated_at"] is not None
    assert body["coin_information"]["symbol"] == "BTC"
    assert body["coin_information"]["price"] == 65000.0
    assert body["deterministic_metrics"]["price_trend"] == "bullish"
    assert body["deterministic_metrics"]["market_cap_tier"] == "large_cap"
    assert body["ai_insights"]["overview"] == ["Bitcoin is trending upward."]


def test_coin_analysis_returns_404_when_coin_unknown(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider, coin_symbol):
        raise coin_analysis_service.UnknownCoinError(coin_symbol)

    monkeypatch.setattr(coin_analysis_service, "generate_coin_analysis", _raise)

    response = client.post("/ai/coin-analysis/ZZZ")

    assert response.status_code == 404
    assert "ZZZ" in response.json()["detail"]


def test_coin_analysis_returns_503_when_provider_unavailable(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider, coin_symbol):
        raise AIProviderUnavailableError("could not reach ollama")

    monkeypatch.setattr(coin_analysis_service, "generate_coin_analysis", _raise)

    response = client.post("/ai/coin-analysis/BTC")

    assert response.status_code == 503


def test_coin_analysis_returns_504_on_timeout(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider, coin_symbol):
        raise AITimeoutError("timed out")

    monkeypatch.setattr(coin_analysis_service, "generate_coin_analysis", _raise)

    response = client.post("/ai/coin-analysis/BTC")

    assert response.status_code == 504


def test_coin_analysis_returns_502_on_invalid_response(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider, coin_symbol):
        raise AIInvalidResponseError("bad shape")

    monkeypatch.setattr(coin_analysis_service, "generate_coin_analysis", _raise)

    response = client.post("/ai/coin-analysis/BTC")

    assert response.status_code == 502


def _sample_gathered_portfolio():
    from ai.models import (
        PortfolioAllocationEntry,
        PortfolioDeterministicMetrics,
        PortfolioHealth,
        PortfolioPosition,
        PortfolioReviewSummary,
    )
    from ai.portfolio_review_service import GatheredPortfolioData

    return GatheredPortfolioData(
        portfolio_summary=PortfolioReviewSummary(
            total_equity=105_000.0,
            cash_balance=20_000.0,
            invested_value=80_000.0,
            holdings_value=85_000.0,
            realized_profit=500.0,
            unrealized_profit=5_000.0,
            total_return_percent=5.0,
            number_of_positions=2,
        ),
        portfolio_health=PortfolioHealth(
            level="good",
            diversification_score=7,
            concentration_risk="medium",
            cash_allocation_percent=19.05,
            largest_holding_symbol="BTC",
            largest_holding_percent=35.0,
        ),
        deterministic_metrics=PortfolioDeterministicMetrics(
            diversification_score=7,
            concentration_risk="medium",
            cash_allocation_percent=19.05,
            largest_position_symbol="BTC",
            largest_position_percent=35.0,
            smallest_position_symbol="ETH",
            smallest_position_percent=15.0,
            top_winner_symbol="BTC",
            top_winner_percent=12.0,
            top_loser_symbol="ETH",
            top_loser_percent=-3.0,
            number_of_positions=2,
        ),
        allocation=[
            PortfolioAllocationEntry(label="BTC", percent=35.0, value=36_750.0),
            PortfolioAllocationEntry(label="ETH", percent=15.0, value=15_750.0),
            PortfolioAllocationEntry(label="CASH", percent=19.05, value=20_000.0),
        ],
        top_positions=[
            PortfolioPosition(
                coin_symbol="BTC",
                coin_name="Bitcoin",
                image_url=None,
                allocation_percent=35.0,
                current_value=36_750.0,
                current_price=65_000.0,
                price_change_percentage_24h=2.1,
                unrealized_percent=12.0,
            ),
        ],
    )


def test_portfolio_review_returns_structured_payload_on_success(monkeypatch):
    from ai.models import PortfolioAIInsights
    from ai.portfolio_review_service import PortfolioReviewResult

    _override_db()
    _override(_StubProvider())  # unused: generate_portfolio_review is monkeypatched below
    monkeypatch.setattr(
        portfolio_review_service,
        "generate_portfolio_review",
        lambda conn, provider: PortfolioReviewResult(
            gathered=_sample_gathered_portfolio(),
            ai_insights=PortfolioAIInsights(
                strengths=["Spread across two positions plus a meaningful cash buffer."],
                weaknesses=["BTC makes up over a third of total equity."],
                interesting_observations=["BTC is the strongest performer at +12.00%."],
                risk_factors=["Concentration risk is medium."],
                educational_notes=["Diversification reduces exposure to any single position."],
            ),
            provider="ollama",
            model="qwen2.5:7b",
            response_time_ms=1450.2,
        ),
    )

    response = client.post("/ai/portfolio-review")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert body["model"] == "qwen2.5:7b"
    assert body["response_time_ms"] == 1450.2
    assert body["generated_at"] is not None
    assert body["portfolio_summary"]["total_equity"] == 105_000.0
    assert body["portfolio_summary"]["number_of_positions"] == 2
    assert body["portfolio_health"]["level"] == "good"
    assert body["portfolio_health"]["diversification_score"] == 7
    assert body["deterministic_metrics"]["largest_position_symbol"] == "BTC"
    assert len(body["allocation"]) == 3
    assert len(body["top_positions"]) == 1
    assert body["ai_insights"]["strengths"] == ["Spread across two positions plus a meaningful cash buffer."]


def test_portfolio_review_returns_503_when_provider_unavailable(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider):
        raise AIProviderUnavailableError("could not reach ollama")

    monkeypatch.setattr(portfolio_review_service, "generate_portfolio_review", _raise)

    response = client.post("/ai/portfolio-review")

    assert response.status_code == 503


def test_portfolio_review_returns_504_on_timeout(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider):
        raise AITimeoutError("timed out")

    monkeypatch.setattr(portfolio_review_service, "generate_portfolio_review", _raise)

    response = client.post("/ai/portfolio-review")

    assert response.status_code == 504


def test_portfolio_review_returns_502_on_invalid_response(monkeypatch):
    _override_db()
    _override(_StubProvider())

    def _raise(conn, provider):
        raise AIInvalidResponseError("bad shape")

    monkeypatch.setattr(portfolio_review_service, "generate_portfolio_review", _raise)

    response = client.post("/ai/portfolio-review")

    assert response.status_code == 502
