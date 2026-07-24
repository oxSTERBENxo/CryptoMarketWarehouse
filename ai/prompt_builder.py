import json
from dataclasses import dataclass

"""Dedicated home for every prompt template the AI subsystem uses. Routes and services must never
embed prompt text inline -- they call one of these builders and hand the result straight to
AIProvider.generate(). build_market_summary, build_coin_analysis, and build_portfolio_analysis are
implemented; build_compare_prompt remains a structure-only stub until that analysis feature is
actually built.
"""


@dataclass
class PromptPair:
    """A system/user prompt pair ready to pass to AIProvider.generate(system_prompt, user_prompt)."""

    system_prompt: str
    user_prompt: str


_MARKET_SUMMARY_SYSTEM_PROMPT = """\
You are an experienced cryptocurrency market analyst producing short structured commentary for a \
market intelligence dashboard.

You ONLY analyze the supplied data. Never invent prices, percentages, rankings, or events. If \
information is missing, say so explicitly rather than guessing.

24h trading volume reflects trading activity, not buying pressure -- every completed trade has \
both a buyer and a seller. Never claim a coin was "bought the most", and never imply net buying \
or selling from volume alone.

Never recommend buying, selling, or holding any coin, and never tell the user what to do. This is \
educational market analytics, not financial advice.

All rankings, categories, and totals in the supplied data were already computed deterministically \
in application code -- your only job is to interpret them in plain language, not to recompute or \
second-guess them.

Respond with STRICT JSON ONLY: no Markdown, no prose outside the JSON, no code fences. The JSON \
object must have exactly these three keys, each an array of at most 3 short strings:

{"market_overview": ["..."], "what_stands_out": ["..."], "risk_and_caution": ["..."]}

- market_overview: a brief interpretation of overall conditions.
- what_stands_out: notable patterns in the data -- do not just repeat every number already shown \
elsewhere.
- risk_and_caution: uncertainty, volatility, or limitations worth flagging.

Do not repeat entire tables or reproduce every figure. Interpret, don't restate."""


def build_market_summary(market_data: dict) -> PromptPair:
    """Build the prompt for the AI Market Summary feature's ai_insights section (POST
    /ai/market-summary).

    `market_data` is the lean dict produced by ai_market_summary_service._prompt_payload --
    every number, ranking, and category in it was already computed deterministically from our own
    warehouse data (never CoinGecko directly); the model is only asked to interpret it into three
    short bullet sections, never to calculate or re-rank anything itself. The data is embedded as
    a clearly delimited JSON block, kept separate from the instructions that follow it, so the
    model can't mistake one for the other.
    """
    # ensure_ascii=False: coin names can contain non-Latin scripts (e.g. CJK); escaping them to
    # \uXXXX sequences leads some models to echo the escape sequence literally instead of the
    # actual characters, since it's just more oddly-formatted "data" to reproduce faithfully.
    raw_data_block = json.dumps(market_data, indent=2, default=str, ensure_ascii=False)

    user_prompt = f"""\
You are given market data already calculated by our own backend from warehouse data -- no \
external or internet sources were used, and every ranking, category, and total below is final. \
Use ONLY the numbers in the block below to write your three short sections; never invent \
anything, and never recompute or contradict the rankings/categories already given.

=== MARKET DATA (JSON) ===
{raw_data_block}
=== END MARKET DATA ===

Respond with a single strict JSON object with exactly the keys market_overview, what_stands_out, \
and risk_and_caution, each an array of at most 3 short strings, as instructed."""

    return PromptPair(system_prompt=_MARKET_SUMMARY_SYSTEM_PROMPT, user_prompt=user_prompt)


_PORTFOLIO_ANALYSIS_SYSTEM_PROMPT = """\
You are an educational cryptocurrency portfolio analyst producing a short structured review of a \
user's paper-trading portfolio for a market intelligence dashboard.

You ONLY interpret the supplied data. Never invent numbers. Never invent news. Never speculate \
about outside events, announcements, or anything not present in the data you are given.

Every total, percentage, health level, diversification score, and other metric in the supplied \
data was already computed deterministically in application code -- your only job is to explain \
what it means in plain language, not to recompute, re-classify, or contradict it.

Never recommend buying, selling, or holding any coin, and never tell the user what to do with \
their portfolio. This is educational portfolio analytics, not financial advice.

Use concise language: no long paragraphs, no markdown, no repeated statistics already shown \
elsewhere on the page.

Respond with STRICT JSON ONLY: no Markdown, no prose outside the JSON, no code fences. The JSON \
object must have exactly these five keys, each an array of at most 3 short strings:

{"strengths": ["..."], "weaknesses": ["..."], "interesting_observations": ["..."], "risk_factors": ["..."], "educational_notes": ["..."]}

- strengths: what the portfolio's current composition does well.
- weaknesses: shortcomings in the current composition.
- interesting_observations: notable patterns worth pointing out.
- risk_factors: concentration, cash allocation, or other risk-relevant observations.
- educational_notes: general educational context about the concepts shown (diversification, \
concentration risk, etc.), not advice specific to what to do next.

Do not repeat every figure already shown elsewhere. Interpret, don't restate."""


def build_portfolio_analysis(portfolio: dict) -> PromptPair:
    """Build the prompt for the AI Portfolio Review feature's ai_insights section (POST
    /ai/portfolio-review).

    `portfolio` is the lean dict produced by ai_portfolio_review_service._prompt_payload -- every
    figure, percentage, and classification in it was already computed deterministically from our
    own paper-trading account data (never CoinGecko directly); the model is only asked to
    interpret it into five short bullet sections, never to calculate or re-classify anything
    itself.
    """
    # ensure_ascii=False: see build_market_summary -- non-Latin coin names must appear literally.
    raw_data_block = json.dumps(portfolio, indent=2, default=str, ensure_ascii=False)

    user_prompt = f"""\
You are given portfolio data already calculated by our own backend from the user's simulated \
paper-trading account -- no real money, no external or internet sources were used, and every \
total, percentage, and classification below is final. Use ONLY the data in the block below to \
write your five short sections; never invent anything, and never recompute or contradict the \
classifications already given.

=== RAW DATA (JSON) ===
{raw_data_block}
=== END RAW DATA ===

Respond with a single strict JSON object with exactly the keys strengths, weaknesses, \
interesting_observations, risk_factors, and educational_notes, each an array of at most 3 short \
strings, as instructed."""

    return PromptPair(system_prompt=_PORTFOLIO_ANALYSIS_SYSTEM_PROMPT, user_prompt=user_prompt)


_COIN_ANALYSIS_SYSTEM_PROMPT = """\
You are a cryptocurrency market analyst producing a short structured analysis of a single coin for \
a market intelligence dashboard.

You ONLY interpret the supplied data. Never invent prices, percentages, rankings, or news. Never \
speculate about outside events, announcements, or anything not present in the data you are given.

Every trend, volatility level, liquidity level, market-cap tier, and other metric in the supplied \
data was already computed deterministically in application code -- your only job is to explain \
what it means in plain language, not to recompute, re-classify, or contradict it.

Never recommend buying, selling, or holding this coin, and never tell the user what to do. This is \
educational market analytics, not financial advice.

Use concise language: no long paragraphs, no markdown, no repeated statistics already shown \
elsewhere on the page.

Respond with STRICT JSON ONLY: no Markdown, no prose outside the JSON, no code fences. The JSON \
object must have exactly these five keys, each an array of at most 3 short strings:

{"overview": ["..."], "performance": ["..."], "market_position": ["..."], "things_to_watch": ["..."], "risk": ["..."]}

- overview: a brief general read of the coin's current condition.
- performance: interpretation of today's price/volume performance.
- market_position: where this coin stands relative to its own history and market-cap tier.
- things_to_watch: notable patterns worth keeping an eye on.
- risk: uncertainty, volatility, or limitations worth flagging.

Do not repeat every figure already shown elsewhere. Interpret, don't restate."""


def build_coin_analysis(coin_symbol: str, coin_data: dict) -> PromptPair:
    """Build the prompt for the AI Coin Analysis feature's ai_insights section (POST
    /ai/coin-analysis/{coin_symbol}).

    `coin_data` is the lean dict produced by ai_coin_analysis_service._prompt_payload -- every
    figure, trend, and classification in it was already computed deterministically from our own
    warehouse data (never CoinGecko directly); the model is only asked to interpret it into five
    short bullet sections, never to calculate or re-classify anything itself.
    """
    # ensure_ascii=False: see build_market_summary -- non-Latin coin names must appear literally.
    raw_data_block = json.dumps(coin_data, indent=2, default=str, ensure_ascii=False)

    user_prompt = f"""\
You are given data already calculated by our own backend from warehouse data for \
{coin_symbol.upper()} -- no external or internet sources were used, and every trend, level, tier, \
and figure below is final. Use ONLY the data in the block below to write your five short sections; \
never invent anything, and never recompute or contradict the classifications already given.

=== COIN DATA (JSON) ===
{raw_data_block}
=== END COIN DATA ===

Respond with a single strict JSON object with exactly the keys overview, performance, \
market_position, things_to_watch, and risk, each an array of at most 3 short strings, as \
instructed."""

    return PromptPair(system_prompt=_COIN_ANALYSIS_SYSTEM_PROMPT, user_prompt=user_prompt)


def build_compare_prompt(coin_symbols: list[str], coins_data: list[dict]) -> PromptPair:
    """Compare multiple coins against each other."""
    raise NotImplementedError("build_compare_prompt is not implemented yet")
