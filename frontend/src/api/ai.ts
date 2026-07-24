import { apiPost } from "./client";
import type { CoinAnalysisResponse, MarketSummaryResponse, PortfolioReviewResponse } from "./types";

/** POST /ai/market-summary — generates a Markdown market summary from warehouse data only
 * (no CoinGecko/internet lookups; see ai_market_summary_service.py). */
export function postMarketSummary(): Promise<MarketSummaryResponse> {
  return apiPost<MarketSummaryResponse>("/ai/market-summary", {});
}

/** POST /ai/coin-analysis/{coinSymbol} — generates a structured AI analysis of one coin from
 * warehouse data only (no CoinGecko/internet lookups; see ai_coin_analysis_service.py). */
export function postCoinAnalysis(coinSymbol: string): Promise<CoinAnalysisResponse> {
  return apiPost<CoinAnalysisResponse>(`/ai/coin-analysis/${encodeURIComponent(coinSymbol)}`, {});
}

/** POST /ai/portfolio-review — generates a structured AI review of the user's paper-trading
 * portfolio from warehouse + paper-trading data only (no CoinGecko/internet lookups; see
 * ai_portfolio_review_service.py). */
export function postPortfolioReview(): Promise<PortfolioReviewResponse> {
  return apiPost<PortfolioReviewResponse>("/ai/portfolio-review", {});
}
