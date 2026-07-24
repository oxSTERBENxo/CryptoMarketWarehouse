// Mirrors the Pydantic response models in analytics_models.py

/** Mirrors the `SortOrder` enum accepted as a query param across analytics endpoints. */
export type SortOrder = "asc" | "desc";

export interface MarketOverview {
  snapshot_date: string;
  coin_count: number;
  total_market_cap_usd: number | null;
  total_volume_24h_usd: number | null;
}

export interface CoinSnapshot {
  coin_id: string;
  symbol: string;
  name: string;
  image_url: string | null;
  snapshot_date: string;
  price_usd: number;
  market_cap_usd: number | null;
  volume_24h_usd: number | null;
  circulating_supply: number | null;
  market_cap_rank: number | null;
}

export interface CurrentMarketCoin {
  coin_id: string;
  symbol: string;
  name: string;
  image_url: string | null;
  price_usd: number;
  price_change_percentage_24h: number | null;
  market_cap_usd: number | null;
  volume_24h_usd: number | null;
  circulating_supply: number | null;
  market_cap_rank: number | null;
}

/** GET /analytics/current-market — live values from the latest ingestion run, independent of
 * the daily dw.fact_market_snapshot grain. Powers the main dashboard's Take New Snapshot refresh. */
export interface CurrentMarketSnapshot {
  refreshed_at: string | null;
  coin_count: number;
  total_market_cap_usd: number | null;
  total_volume_24h_usd: number | null;
  coins: CurrentMarketCoin[];
}

export interface TopMarketCapEntry {
  market_cap_position: number;
  coin_id: string;
  symbol: string;
  name: string;
  image_url: string | null;
  snapshot_date: string;
  market_cap_usd: number | null;
  price_usd: number;
}

export interface TopVolumeEntry {
  volume_position: number;
  coin_id: string;
  symbol: string;
  name: string;
  image_url: string | null;
  snapshot_date: string;
  volume_24h_usd: number | null;
  price_usd: number;
}

export interface IntradaySnapshot {
  coin_id: string;
  symbol: string;
  name: string;
  image_url: string | null;
  observation_timestamp: string;
  price_usd: number;
  market_cap_usd: number | null;
  volume_24h_usd: number | null;
}

export interface CoinHistorySummary {
  coin_id: string;
  symbol: string;
  name: string;
  period_start_date: string;
  period_end_date: string;
  period_start_price: number;
  period_end_price: number;
  absolute_change: number;
  percent_change: number | null;
  min_price: number;
  max_price: number;
  avg_price: number;
  observation_count: number;
}

/** Mirrors the `LeadersPeriod` enum accepted by GET /analytics/market-leaders. */
export type LeadersPeriod = "today" | "7d" | "30d" | "90d" | "1y";

export interface MarketMoverEntry {
  coin_id: string;
  symbol: string;
  name: string;
  image_url: string | null;
  start_price: number;
  end_price: number;
  percent_change: number | null;
  high_price: number;
  low_price: number;
  volatility_percent: number | null;
  volume_24h_usd: number | null;
  market_cap_usd: number | null;
  market_cap_rank: number | null;
  observation_count: number;
}

export interface MarketLeadersSummary {
  total_tracked_coins: number;
  latest_update_at: string | null;
  today_best_performer: MarketMoverEntry | null;
  today_worst_performer: MarketMoverEntry | null;
  average_market_movement_percent: number | null;
}

export interface MarketLeadersCoverage {
  qualifying_coin_count: number;
  earliest_observation: string | null;
  latest_observation: string | null;
  empty_reason: string | null;
}

export interface MarketLeadersResponse {
  period: LeadersPeriod;
  period_start: string | null;
  period_end: string | null;
  gainers: MarketMoverEntry[];
  losers: MarketMoverEntry[];
  highest_volume: MarketMoverEntry | null;
  highest_ranked: MarketMoverEntry | null;
  most_volatile: MarketMoverEntry | null;
  summary: MarketLeadersSummary;
  coverage: MarketLeadersCoverage;
}

// Mirrors the Pydantic request/response models in portfolio_models.py

export interface Portfolio {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Holding {
  id: number;
  portfolio_id: number;
  coin_symbol: string;
  coin_name: string | null;
  image_url: string | null;
  price_change_percentage_24h: number | null;
  quantity: number;
  average_buy_price: number;
  current_price: number | null;
  current_value: number | null;
  cost_basis: number;
  unrealized_profit: number | null;
  profit_percent: number | null;
  created_at: string;
  updated_at: string;
}

export interface PortfolioSummary {
  total_value: number;
  total_cost_basis: number;
  total_unrealized_profit: number;
  total_unrealized_percent: number | null;
}

export interface PortfolioDetail extends Portfolio {
  holdings: Holding[];
  summary: PortfolioSummary;
}

export interface PortfolioCreateRequest {
  name: string;
  description?: string | null;
}

export type PortfolioUpdateRequest = PortfolioCreateRequest;

export interface HoldingCreateRequest {
  coin_symbol: string;
  quantity: number;
  average_buy_price: number;
}

export interface HoldingUpdateRequest {
  quantity: number;
  average_buy_price: number;
}

// Mirrors the Pydantic request/response models in paper_trading_models.py

export interface PaperAccount {
  id: number;
  name: string;
  initial_cash: number;
  cash_balance: number;
  created_at: string;
  updated_at: string;
}

export type PaperTransactionType = "BUY" | "SELL";

export interface PaperTransaction {
  id: number;
  account_id: number;
  coin_symbol: string;
  transaction_type: PaperTransactionType;
  quantity: number;
  execution_price: number;
  total_value: number;
  realized_profit: number | null;
  executed_at: string;
}

export interface PaperHolding {
  coin_symbol: string;
  coin_name: string | null;
  image_url: string | null;
  price_change_percentage_24h: number | null;
  quantity: number;
  average_cost: number;
  current_price: number | null;
  current_value: number | null;
  unrealized_profit: number | null;
  unrealized_percent: number | null;
  allocation_percent: number | null;
}

export interface PaperPortfolio {
  account: PaperAccount;
  holdings: PaperHolding[];
  cash_balance: number;
  invested_value: number;
  holdings_value: number;
  total_equity: number;
  realized_profit: number;
  unrealized_profit: number;
  total_return_percent: number | null;
  best_performer: string | null;
  worst_performer: string | null;
}

export interface TradeRequest {
  coin_symbol: string;
  quantity: number;
}

/** Mirrors the /health/scheduler response shape (see scheduler.get_scheduler_status in the backend). */
export interface SchedulerHealth {
  enabled: boolean;
  running: boolean;
  interval_minutes: number;
  currently_running: boolean;
  last_success_at: string | null;
  last_failure_at: string | null;
  next_run_time: string | null;
}

// Mirrors the Pydantic response models in warehouse_health_models.py (GET /health/warehouse)

export type HealthState = "healthy" | "warning" | "error" | "unknown";

export interface HealthCheck {
  status: HealthState;
  message: string;
}

export interface EtlRunInfo {
  run_id: number;
  pipeline_name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
}

export interface StaleCoin {
  coin_id: string;
  symbol: string;
  last_seen_date: string | null;
}

/** GET /health/warehouse — always returns HTTP 200; a degraded warehouse is carried in
 * overall_status/the per-check status fields, not an HTTP error, so a real outage (fetch itself
 * failing) is still distinguishable from "the warehouse reports a problem". */
export interface WarehouseHealthResponse {
  generated_at: string;
  environment: string;
  overall_status: HealthState;

  database: HealthCheck;
  latest_successful_run: EtlRunInfo | null;
  latest_failed_run: EtlRunInfo | null;

  last_daily_snapshot_date: string | null;
  last_hourly_snapshot_at: string | null;
  daily_fact_row_count: number;
  hourly_fact_row_count: number;
  current_coin_count: number;
  historical_coin_version_count: number;

  recent_failed_run_count: number;
  data_quality: HealthCheck;
  duplicate_check: HealthCheck;

  missing_date_coverage: HealthCheck;
  missing_dates: string[];

  stale_coin_check: HealthCheck;
  stale_coins: StaleCoin[];

  scheduler: HealthCheck;
  scheduler_status: SchedulerHealth;
}

// Mirrors the Pydantic response models in ai_models.py

export type MarketDirection = "positive" | "negative" | "mixed" | "neutral";
export type AttentionCategory = "positive_momentum" | "most_active" | "unusual_activity";

/** Deterministic (no-AI) overall market read -- direction/headline/counts are all computed in
 * ai_market_summary_service.determine_market_direction / gather_market_data, never by the model. */
export interface MarketStatus {
  direction: MarketDirection;
  headline: string;
  average_change_24h: number | null;
  gainers_count: number;
  losers_count: number;
  unchanged_count: number;
  coins_tracked: number;
  snapshot_time: string | null;
}

export interface MarketMetrics {
  total_market_cap: number | null;
  total_volume_24h: number | null;
}

/** One coin row shared by attention_coins/top_gainers/top_losers/most_active. volume_share_percent
 * is this coin's share of metrics.total_volume_24h, when both are known. */
export interface MarketCoinEntry {
  coin_id: string;
  name: string;
  symbol: string;
  image_url: string | null;
  price: number;
  change_24h: number | null;
  volume_24h: number | null;
  market_cap: number | null;
  market_cap_rank: number | null;
  volume_share_percent: number | null;
}

export interface AttentionCoin extends MarketCoinEntry {
  category: AttentionCategory;
  /** Short deterministic explanation, e.g. "Highest 24h trading volume among tracked coins." --
   * never a buy/sell recommendation. */
  reason: string;
}

/** The only AI-authored part of the response -- an interpretation of the already-computed data
 * above, not a source of any ranking/total itself. Falls back to a deterministic template
 * (still populated, never empty) if the model's response couldn't be parsed as valid JSON. */
export interface AIInsights {
  market_overview: string[];
  what_stands_out: string[];
  risk_and_caution: string[];
}

/** POST /ai/market-summary response. Structured market intelligence, not a Markdown blob --
 * render each section with dedicated components, never dangerouslySetInnerHTML. */
export interface MarketSummaryResponse {
  generated_at: string;
  provider: string;
  model: string;
  response_time_ms: number;
  market_status: MarketStatus;
  metrics: MarketMetrics;
  attention_coins: AttentionCoin[];
  top_gainers: MarketCoinEntry[];
  top_losers: MarketCoinEntry[];
  most_active: MarketCoinEntry[];
  ai_insights: AIInsights;
}

// POST /ai/coin-analysis/{coin_symbol} -- mirrors the CoinAnalysis* Pydantic models in ai_models.py

export type PriceTrend = "bullish" | "bearish" | "neutral" | "unknown";
export type VolatilityLevel = "low" | "medium" | "high" | "unknown";
export type LiquidityLevel = "low" | "medium" | "high" | "unknown";
export type MarketCapTier = "large_cap" | "mid_cap" | "small_cap" | "micro_cap" | "unknown";
export type VolumeTrend = "rising" | "falling" | "stable" | "unknown";

/** Every raw warehouse figure for one coin -- the live current-market snapshot plus how much
 * loaded daily history backs the deterministic metrics below. */
export interface CoinInformation {
  coin_id: string;
  symbol: string;
  name: string;
  image_url: string | null;
  price: number;
  change_24h: number | null;
  market_cap: number | null;
  market_cap_rank: number | null;
  volume_24h: number | null;
  circulating_supply: number | null;
  history_observation_count: number;
  history_start_date: string | null;
  history_end_date: string | null;
}

/** Every interpretive figure computed deterministically in ai_coin_analysis_service.py -- the AI
 * is only ever asked to explain these, never to calculate or override them. */
export interface CoinDeterministicMetrics {
  price_trend: PriceTrend;
  trend_percent_change: number | null;
  momentum_24h_percent: number | null;
  volatility_level: VolatilityLevel;
  volatility_percent: number | null;
  liquidity_level: LiquidityLevel;
  liquidity_ratio_percent: number | null;
  market_cap_tier: MarketCapTier;
  volume_trend: VolumeTrend;
  average_daily_movement_percent: number | null;
  period_high: number | null;
  period_low: number | null;
  distance_from_high_percent: number | null;
  distance_from_low_percent: number | null;
}

/** The only AI-authored part of the Coin Analysis response -- five short bullet sections
 * interpreting CoinInformation/CoinDeterministicMetrics, never a source of any figure itself.
 * Falls back to a deterministic template (still populated, never empty) if the model's response
 * couldn't be parsed as valid JSON. */
export interface CoinAIInsights {
  overview: string[];
  performance: string[];
  market_position: string[];
  things_to_watch: string[];
  risk: string[];
}

export interface CoinAnalysisResponse {
  generated_at: string;
  provider: string;
  model: string;
  response_time_ms: number;
  coin_information: CoinInformation;
  deterministic_metrics: CoinDeterministicMetrics;
  ai_insights: CoinAIInsights;
}

// POST /ai/portfolio-review -- mirrors the Portfolio* Pydantic models in ai_models.py

export type PortfolioHealthLevel = "excellent" | "good" | "balanced" | "concentrated" | "high_risk" | "very_high_risk";
export type ConcentrationRisk = "low" | "medium" | "high" | "unknown";

/** Every raw valuation figure for the review, sourced from the user's existing paper-trading
 * account (the same data the Portfolio page's Paper Trading tab already displays). */
export interface PortfolioReviewSummary {
  total_equity: number;
  cash_balance: number;
  invested_value: number;
  holdings_value: number;
  realized_profit: number;
  unrealized_profit: number;
  total_return_percent: number | null;
  number_of_positions: number;
}

/** The headline deterministic classification -- see ai_portfolio_review_service.classify_portfolio_health
 * for exactly how `level` is derived from diversification_score and concentration_risk. */
export interface PortfolioHealth {
  level: PortfolioHealthLevel;
  diversification_score: number;
  concentration_risk: ConcentrationRisk;
  cash_allocation_percent: number;
  largest_holding_symbol: string | null;
  largest_holding_percent: number | null;
}

/** Every interpretive figure computed deterministically in ai_portfolio_review_service.py -- the
 * AI is only ever asked to explain these, never to calculate or override them. */
export interface PortfolioDeterministicMetrics {
  diversification_score: number;
  concentration_risk: ConcentrationRisk;
  cash_allocation_percent: number;
  largest_position_symbol: string | null;
  largest_position_percent: number | null;
  smallest_position_symbol: string | null;
  smallest_position_percent: number | null;
  top_winner_symbol: string | null;
  top_winner_percent: number | null;
  top_loser_symbol: string | null;
  top_loser_percent: number | null;
  number_of_positions: number;
}

/** One slice of the portfolio's allocation breakdown -- every held coin plus a final "CASH"
 * entry, percents summing to ~100% of total_equity. */
export interface PortfolioAllocationEntry {
  label: string;
  percent: number;
  value: number;
}

/** One holding for the "Top Holdings" cards -- allocation-ranked, capped server-side. */
export interface PortfolioPosition {
  coin_symbol: string;
  coin_name: string | null;
  image_url: string | null;
  allocation_percent: number | null;
  current_value: number | null;
  current_price: number | null;
  price_change_percentage_24h: number | null;
  unrealized_percent: number | null;
}

/** The only AI-authored part of the Portfolio Review response -- five short bullet sections
 * interpreting PortfolioReviewSummary/PortfolioHealth/PortfolioDeterministicMetrics, never a
 * source of any figure itself. Falls back to a deterministic template (still populated, never
 * empty) if the model's response couldn't be parsed as valid JSON. */
export interface PortfolioAIInsights {
  strengths: string[];
  weaknesses: string[];
  interesting_observations: string[];
  risk_factors: string[];
  educational_notes: string[];
}

export interface PortfolioReviewResponse {
  generated_at: string;
  provider: string;
  model: string;
  response_time_ms: number;
  portfolio_summary: PortfolioReviewSummary;
  portfolio_health: PortfolioHealth;
  deterministic_metrics: PortfolioDeterministicMetrics;
  allocation: PortfolioAllocationEntry[];
  top_positions: PortfolioPosition[];
  ai_insights: PortfolioAIInsights;
}

// ---------------------------------------------------------------------------
// Analytics Explorer (mirrors analytics_explorer_models.py)
// ---------------------------------------------------------------------------

export type ExplorerMetric = "price" | "volume" | "market_cap" | "market_cap_rank" | "volatility";

export type ExplorerCondition =
  | "increased_by_percent"
  | "decreased_by_percent"
  | "increased_by_amount"
  | "decreased_by_amount"
  | "improved_by"
  | "declined_by"
  | "top_n"
  | "bottom_n";

export type ExplorerSortField =
  | "percent_change"
  | "dollar_change"
  | "end_price"
  | "avg_volume"
  | "rank_change"
  | "market_cap"
  | "volatility";

/** Optional value filters applied before the analysis condition. All bounds inclusive. */
export interface ExplorerFilters {
  min_market_cap?: number;
  max_market_cap?: number;
  min_avg_volume?: number;
  min_rank?: number;
  max_rank?: number;
  min_price?: number;
  max_price?: number;
}

export interface ExplorerRequest {
  metric: ExplorerMetric;
  condition: ExplorerCondition;
  from_date: string;
  to_date: string;
  threshold?: number | null;
  filters?: ExplorerFilters;
  /** Omit to use the analysis's natural sort (e.g. percent change desc for top gainers). */
  sort_by?: ExplorerSortField | null;
  sort_order?: SortOrder;
  limit?: number;
  offset?: number;
}

/** One qualifying coin with the full set of period statistics. start/end values are the
 * first/last real observation inside the requested range -- never estimated. */
export interface ExplorerResultRow {
  coin_id: string;
  symbol: string;
  name: string;
  image_url: string | null;
  start_date: string;
  end_date: string;
  start_price: number;
  end_price: number;
  dollar_change: number;
  percent_change: number | null;
  low_price: number;
  high_price: number;
  avg_price: number | null;
  avg_volume: number | null;
  volatility_percent: number | null;
  start_rank: number | null;
  end_rank: number | null;
  /** start_rank - end_rank: positive means the coin improved (moved toward #1). */
  rank_change: number | null;
  market_cap_usd: number | null;
  observation_count: number;
}

/** Deterministic aggregates over every qualifying row (not just the current page). */
export interface ExplorerSummary {
  results_found: number;
  average_percent_change: number | null;
  largest_increase_percent: number | null;
  largest_increase_symbol: string | null;
  largest_decrease_percent: number | null;
  largest_decrease_symbol: string | null;
  average_volume: number | null;
}

export interface ExplorerResponse {
  analysis_label: string;
  metric: ExplorerMetric;
  condition: ExplorerCondition;
  from_date: string;
  to_date: string;
  threshold: number | null;
  sort_by: ExplorerSortField;
  sort_order: SortOrder;
  total_results: number;
  offset: number;
  limit: number;
  summary: ExplorerSummary;
  rows: ExplorerResultRow[];
}
