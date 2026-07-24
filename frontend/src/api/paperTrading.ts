import { apiGet, apiPost } from "./client";
import type { PaperAccount, PaperPortfolio, PaperTransaction, TradeRequest } from "./types";

/** GET /paper-account */
export function getPaperAccount(): Promise<PaperAccount> {
  return apiGet<PaperAccount>("/paper-account");
}

/** POST /paper-account/reset */
export function resetPaperAccount(): Promise<PaperAccount> {
  return apiPost<PaperAccount>("/paper-account/reset", {});
}

/** GET /paper-portfolio */
export function getPaperPortfolio(): Promise<PaperPortfolio> {
  return apiGet<PaperPortfolio>("/paper-portfolio");
}

/** POST /paper-trades/buy */
export function buyPaperTrade(body: TradeRequest): Promise<PaperTransaction> {
  return apiPost<PaperTransaction>("/paper-trades/buy", body);
}

/** POST /paper-trades/sell */
export function sellPaperTrade(body: TradeRequest): Promise<PaperTransaction> {
  return apiPost<PaperTransaction>("/paper-trades/sell", body);
}

/** GET /paper-trades */
export function getPaperTrades(limit?: number): Promise<PaperTransaction[]> {
  return apiGet<PaperTransaction[]>("/paper-trades", { limit });
}
