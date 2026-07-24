import { apiGet } from "./client";
import type {
  CoinHistorySummary,
  CoinSnapshot,
  CurrentMarketSnapshot,
  IntradaySnapshot,
  LeadersPeriod,
  MarketLeadersResponse,
  MarketOverview,
  SortOrder,
  TopMarketCapEntry,
  TopVolumeEntry,
} from "./types";

/** GET /analytics/overview */
export function getOverview(): Promise<MarketOverview> {
  return apiGet<MarketOverview>("/analytics/overview");
}

/** GET /analytics/latest */
export function getLatest(limit?: number): Promise<CoinSnapshot[]> {
  return apiGet<CoinSnapshot[]>("/analytics/latest", { limit });
}

/** GET /analytics/current-market — live current values from the latest ingestion run, not the
 * daily-grain warehouse fact table. Powers the main dashboard's Take New Snapshot refresh. */
export function getCurrentMarket(limit?: number): Promise<CurrentMarketSnapshot> {
  return apiGet<CurrentMarketSnapshot>("/analytics/current-market", { limit });
}

/** GET /analytics/top-market-cap */
export function getTopMarketCap(limit?: number): Promise<TopMarketCapEntry[]> {
  return apiGet<TopMarketCapEntry[]>("/analytics/top-market-cap", { limit });
}

/** GET /analytics/top-volume */
export function getTopVolume(limit?: number): Promise<TopVolumeEntry[]> {
  return apiGet<TopVolumeEntry[]>("/analytics/top-volume", { limit });
}

export interface HistoryParams {
  limit?: number;
  order?: SortOrder;
  /** ISO date (YYYY-MM-DD). Only include snapshots on or after this date. */
  fromDate?: string;
  /** ISO date (YYYY-MM-DD). Only include snapshots on or before this date. */
  toDate?: string;
}

/** GET /analytics/history/{coin_symbol} — matched case-insensitively by the backend. */
export function getHistory(coinSymbol: string, params: HistoryParams = {}): Promise<CoinSnapshot[]> {
  return apiGet<CoinSnapshot[]>(`/analytics/history/${encodeURIComponent(coinSymbol)}`, {
    limit: params.limit,
    order: params.order,
    from_date: params.fromDate,
    to_date: params.toDate,
  });
}

export interface HistorySummaryParams {
  /** ISO date (YYYY-MM-DD). Only include snapshots on or after this date. */
  fromDate?: string;
  /** ISO date (YYYY-MM-DD). Only include snapshots on or before this date. */
  toDate?: string;
}

/** GET /analytics/history/{coin_symbol}/summary — period stats computed server-side. */
export function getHistorySummary(
  coinSymbol: string,
  params: HistorySummaryParams = {}
): Promise<CoinHistorySummary> {
  return apiGet<CoinHistorySummary>(`/analytics/history/${encodeURIComponent(coinSymbol)}/summary`, {
    from_date: params.fromDate,
    to_date: params.toDate,
  });
}

/** GET /analytics/intraday/{coin_symbol}/today — today's (current UTC date) intraday observations, chronological. */
export function getIntradayToday(coinSymbol: string): Promise<IntradaySnapshot[]> {
  return apiGet<IntradaySnapshot[]>(`/analytics/intraday/${encodeURIComponent(coinSymbol)}/today`);
}

/** GET /analytics/market-leaders — gainer/loser rankings and highlight stats for a period. */
export function getMarketLeaders(period: LeadersPeriod, limit?: number): Promise<MarketLeadersResponse> {
  return apiGet<MarketLeadersResponse>("/analytics/market-leaders", { period, limit });
}
