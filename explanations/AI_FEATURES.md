# AI Features

Three features layer AI-authored interpretation on top of deterministic, already-computed
warehouse data: **AI Market Summary** (Dashboard), **AI Coin Analysis** (Coin Details), and **AI
Portfolio Review** (Portfolio → Paper Trading). This document explains the shared architecture and
the deterministic-vs-AI split every one of them follows.

## The one rule: the model never calculates anything

For all three features, every number, trend, tier, or classification shown to the user is computed
in plain Python from data already in the warehouse (`analytics_repository`, `paper_trading_service`)
**before** the AI provider is ever called. The prompt sent to the model hands over that already-
computed data and asks only for a short, structured interpretation of it — the model is never asked
to compute a percent change, decide a trend, or invent a number. `ai/prompt_builder.py`'s system
prompts state this explicitly ("never recompute, never invent a figure"), and every service's
Pydantic response model separates the two halves of the response (e.g.
`CoinAnalysisResponse.deterministic_metrics` vs `.ai_insights`) so a frontend consumer can never
confuse which part came from where.

This matters for a warehouse project specifically: the AI layer can fail, time out, or hallucinate
formatting, and the user still sees a fully correct, fully populated set of figures — only the
handful of interpretive bullet points are affected.

## Provider architecture

```
ai_config.get_ai_provider()  -- the ONLY place that reads AI_PROVIDER/provider env vars
        |
        v
   AIProvider (ai/provider.py) -- abstract interface: generate(system_prompt, user_prompt)
        |
        v
   OllamaProvider / GroqProvider
```

Every route/service calls `get_ai_provider()` and only ever touches the `AIProvider` interface —
nothing else in the app knows or cares which concrete backend is active. `AI_PROVIDER=ollama`
uses `OLLAMA_BASE_URL`/`OLLAMA_MODEL`; `AI_PROVIDER=groq` uses `GROQ_API_KEY`/`GROQ_MODEL`.
Adding another provider later means one new provider module plus a config change in `ai/config.py`,
never a change to the three feature services or their routes.

Each provider maps every failure mode to one of `ai/provider.py`'s typed exceptions
(`AIProviderUnavailableError`, `AITimeoutError`, `AIModelNotFoundError`, `AIInvalidResponseError`)
so callers never handle a raw `requests` exception. `ai/routes.py` maps those to HTTP status codes:
unavailable → 503, timeout → 504, anything else → 502.

## The three features

| Feature | Route | Data source | Deterministic figures | AI-authored |
|---|---|---|---|---|
| Market Summary | `POST /ai/market-summary` | `analytics_repository` (live current-market snapshot) | Direction (positive/negative/mixed/neutral), gainers/losers/most-active ranking, momentum/unusual-activity flags | `market_overview`, `what_stands_out`, `risk_and_caution` bullets |
| Coin Analysis | `POST /ai/coin-analysis/{symbol}` | `analytics_repository` (live snapshot + full history) | Price trend, volatility level, liquidity level, market-cap tier, volume trend, average daily movement, distance from period high/low | `overview`, `performance`, `market_position`, `things_to_watch`, `risk` bullets |
| Portfolio Review | `POST /ai/portfolio-review` | `paper_trading_service.get_portfolio()` (the paper-trading account, not manual holdings) | Diversification score (HHI-based), concentration-risk classification, combined portfolio-health rating, top/worst positions | `strengths`, `weaknesses`, `interesting_observations`, `risk_factors`, `educational_notes` bullets |

Every deterministic classifier reports `"unknown"` rather than guessing when there isn't enough
data yet (e.g. a coin tracked for the first time today has no history to compute volatility from) —
an honest state, not an estimate.

## Fallback when the AI response can't be parsed

The model is asked for strict JSON matching a fixed shape. If it returns something that doesn't
parse (truncated output, prose instead of JSON, a schema mismatch), each service substitutes a
fully deterministic, non-AI fallback text (still fully populated, e.g.
`_fallback_ai_insights`/`_fallback_coin_insights`/`_fallback_portfolio_insights`) that explicitly
says AI commentary is temporarily unavailable, while every deterministic figure is unaffected. This
is a different failure mode from the provider being unreachable/timing out (which surfaces as an
HTTP 503/504 — see "Provider architecture" above): a malformed-but-received response degrades
gracefully in place; the request itself never fails.

## Frontend

Each feature is a self-contained card (`AIMarketSummaryCard`, `AICoinAnalysisCard`,
`AIPortfolioReviewCard`) with its own skeleton loading state, "Generate"/"Refresh" affordance (AI
calls are user-triggered on demand, not automatic on page load, since each is a real LLM round
trip), and a `GET /ai/health` check surfaced as a status badge. A refresh that fails preserves the
previously-shown content rather than blanking the card.
