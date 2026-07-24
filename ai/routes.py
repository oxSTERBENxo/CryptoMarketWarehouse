from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from ai import coin_analysis_service
from ai import config as ai_config
from ai import market_summary_service
from ai import portfolio_review_service
from ai.models import (
    AIHealthResponse,
    AIProviderInfo,
    AIProvidersResponse,
    CoinAnalysisResponse,
    MarketSummaryResponse,
    PortfolioReviewResponse,
)
from ai.provider import AIProvider, AIProviderError, AIProviderUnavailableError, AITimeoutError
from database import get_connection

router = APIRouter(prefix="/ai", tags=["ai"])

# Known provider names the factory can eventually support, independent of which ones are actually
# implemented yet -- lets /ai/providers show the whole roadmap, not just what's wired up today.
_KNOWN_PROVIDERS = ("ollama", "groq", "openai", "gemini")
_IMPLEMENTED_PROVIDERS = ("ollama", "groq")

_HEALTH_SYSTEM_PROMPT = "You are a health-check responder. Reply with exactly one word."
_HEALTH_USER_PROMPT = "Reply with exactly one word: ok"


def _get_provider() -> AIProvider:
    return ai_config.get_ai_provider()


def _get_db():
    """Yield a connection for one request; convert a failure to *connect* into a 503. Same
    guarded-connect-only pattern as analytics/routes.py's _get_db / portfolio/routes.py's _get_db."""
    try:
        conn = get_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    with conn:
        yield conn


DbDep = Annotated[Connection, Depends(_get_db)]


def _to_http_exception(exc: AIProviderError) -> HTTPException:
    """Shared AIProviderError -> HTTPException mapping, used by every route that calls
    AIProvider.generate() so a provider failure always surfaces as a structured error response,
    never a raw crash."""
    if isinstance(exc, AIProviderUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, AITimeoutError):
        return HTTPException(status_code=504, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@router.get(
    "/health",
    response_model=AIHealthResponse,
    summary="Check that the active AI provider can answer a prompt",
    description=(
        "Sends one trivial prompt through the currently configured provider (see AI_PROVIDER) and "
        "reports whether it answered, how long it took, and which model served it. Does not "
        "perform any market/portfolio analysis -- see POST /ai/market-summary for that."
    ),
)
def ai_health(provider: AIProvider = Depends(_get_provider)) -> AIHealthResponse:
    try:
        result = provider.generate(_HEALTH_SYSTEM_PROMPT, _HEALTH_USER_PROMPT)
    except AIProviderError as exc:
        raise _to_http_exception(exc) from exc

    return AIHealthResponse(
        provider=result.provider,
        model=result.model,
        healthy=True,
        response_time_ms=result.response_time_ms,
    )


@router.get(
    "/providers",
    response_model=AIProvidersResponse,
    summary="List known AI providers and which one is active",
    description="Static info only -- does not contact any provider. Use /ai/health to verify the active one actually responds.",
)
def ai_providers() -> AIProvidersResponse:
    provider_details = {
        "ollama": f"{ai_config.OLLAMA_BASE_URL} ({ai_config.OLLAMA_MODEL})",
        "groq": f"{ai_config.GROQ_MODEL} ({'API key set' if ai_config.GROQ_API_KEY else 'missing GROQ_API_KEY'})",
    }
    providers = [
        AIProviderInfo(
            name=name,
            active=name == ai_config.AI_PROVIDER,
            configured=name in _IMPLEMENTED_PROVIDERS,
            detail=provider_details.get(name, "not implemented yet"),
        )
        for name in _KNOWN_PROVIDERS
    ]
    return AIProvidersResponse(active_provider=ai_config.AI_PROVIDER, providers=providers)


@router.post(
    "/market-summary",
    response_model=MarketSummaryResponse,
    summary="Generate an AI-written summary of the current market, from warehouse data only",
    description=(
        "Gathers live current-market data already in the warehouse (analytics.current_market_live, "
        "via analytics/repository.py's fetch_current_market -- the same source the dashboard's live view "
        "uses) and computes market direction, top gainers/losers, most-actively-traded coins, and "
        "'attention' coins (positive momentum / most active / unusual activity) entirely "
        "deterministically in application code -- see ai/market_summary_service.py. The AI provider "
        "only interprets those already-final numbers into three short bullet sections "
        "(ai_insights); it never decides any ranking, category, or total, and a malformed AI "
        "response degrades to a deterministic fallback rather than failing the request. Never "
        "calls CoinGecko or any external source directly. Returns 404 if nothing has been "
        "ingested yet, or a provider error (503/504/502) if the AI backend is unreachable, times "
        "out, or returns an unusable response."
    ),
)
def ai_market_summary(conn: DbDep, provider: AIProvider = Depends(_get_provider)) -> MarketSummaryResponse:
    try:
        result = market_summary_service.generate_market_summary(conn, provider)
    except market_summary_service.NoMarketDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise _to_http_exception(exc) from exc

    gathered = result.gathered
    return MarketSummaryResponse(
        generated_at=datetime.now(timezone.utc),
        provider=result.provider,
        model=result.model,
        response_time_ms=result.response_time_ms,
        market_status=gathered.market_status,
        metrics=gathered.metrics,
        attention_coins=gathered.attention_coins,
        top_gainers=gathered.top_gainers,
        top_losers=gathered.top_losers,
        most_active=gathered.most_active,
        ai_insights=result.ai_insights,
    )


@router.post(
    "/coin-analysis/{coin_symbol}",
    response_model=CoinAnalysisResponse,
    summary="Generate an AI-written analysis of one coin, from warehouse data only",
    description=(
        "Gathers the live current-market snapshot and full loaded daily history for one coin "
        "(analytics/repository.py's fetch_live_prices_for_symbols / fetch_history_summary / "
        "fetch_history) and computes price trend, volatility, liquidity, market-cap tier, volume "
        "trend, average daily movement, and distance from the tracked period high/low entirely "
        "deterministically in application code -- see ai/coin_analysis_service.py. The AI provider "
        "only interprets those already-final figures into five short bullet sections "
        "(ai_insights); it never decides any classification or number, and a malformed AI response "
        "degrades to a deterministic fallback rather than failing the request. Never calls "
        "CoinGecko or any external source directly. Returns 404 if coin_symbol has no current live "
        "warehouse snapshot, or a provider error (503/504/502) if the AI backend is unreachable, "
        "times out, or returns an unusable response."
    ),
)
def ai_coin_analysis(
    coin_symbol: str, conn: DbDep, provider: AIProvider = Depends(_get_provider)
) -> CoinAnalysisResponse:
    try:
        result = coin_analysis_service.generate_coin_analysis(conn, provider, coin_symbol)
    except coin_analysis_service.UnknownCoinError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise _to_http_exception(exc) from exc

    gathered = result.gathered
    return CoinAnalysisResponse(
        generated_at=datetime.now(timezone.utc),
        provider=result.provider,
        model=result.model,
        response_time_ms=result.response_time_ms,
        coin_information=gathered.coin_information,
        deterministic_metrics=gathered.deterministic_metrics,
        ai_insights=result.ai_insights,
    )


@router.post(
    "/portfolio-review",
    response_model=PortfolioReviewResponse,
    summary="Generate an AI-written review of the user's paper-trading portfolio, from warehouse data only",
    description=(
        "Gathers the user's existing simulated paper-trading account valuation "
        "(paper_trading/service.py's get_portfolio -- the same data the Portfolio page's Paper Trading "
        "tab already displays) and computes diversification score, concentration risk, cash "
        "allocation, largest/smallest position, top winner/loser, and an overall portfolio health "
        "level entirely deterministically in application code -- see "
        "ai/portfolio_review_service.py. The AI provider only interprets those already-final "
        "figures into five short bullet sections (ai_insights); it never decides any "
        "classification or number, never recommends buying/selling/holding anything, and a "
        "malformed AI response degrades to a deterministic fallback rather than failing the "
        "request. Never calls CoinGecko or any external source directly. An empty (all-cash) "
        "portfolio is a valid response, not an error. Returns a provider error (503/504/502) if "
        "the AI backend is unreachable, times out, or returns an unusable response."
    ),
)
def ai_portfolio_review(conn: DbDep, provider: AIProvider = Depends(_get_provider)) -> PortfolioReviewResponse:
    try:
        result = portfolio_review_service.generate_portfolio_review(conn, provider)
    except AIProviderError as exc:
        raise _to_http_exception(exc) from exc

    gathered = result.gathered
    return PortfolioReviewResponse(
        generated_at=datetime.now(timezone.utc),
        provider=result.provider,
        model=result.model,
        response_time_ms=result.response_time_ms,
        portfolio_summary=gathered.portfolio_summary,
        portfolio_health=gathered.portfolio_health,
        deterministic_metrics=gathered.deterministic_metrics,
        allocation=gathered.allocation,
        top_positions=gathered.top_positions,
        ai_insights=result.ai_insights,
    )
