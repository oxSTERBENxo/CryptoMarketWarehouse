import { apiGet, apiPost } from "./client";

export interface RefreshMarketDataResult {
  status: string;
  /** Coins fetched from CoinGecko this run. */
  coins_fetched: number;
  /** Rows landed in staging.coingecko_market_snapshot (the source live values come from). */
  staging_rows_inserted: number;
  /** New dw.fact_market_snapshot rows -- 0 on a same-day repeat run thanks to the warehouse's
   * (date_key, coin_key) idempotency guard, even though coins_fetched/staging_rows_inserted > 0. */
  daily_snapshots_inserted: number;
  /** New dw.fact_market_intraday rows -- one per successfully-fetched coin, > 0 on every
   * successful press regardless of daily_snapshots_inserted (Part 10). */
  intraday_snapshots_inserted: number;
  /** dw.dim_coin rows inserted or SCD2-updated. */
  coins_updated: number;
  /** Startup recovery job's state at call time -- not backfilled by this endpoint itself. */
  missing_dates_found: number;
  dates_backfilled: number;
  dates_skipped: number;
  elapsed_seconds: number;
  refreshed_at: string | null;
  /** Total dw.fact_market_intraday rows for today, across every run. */
  intraday_snapshots_today: number;
  errors: string[];
}

/** POST /admin/refresh-market-data — runs the existing incremental ingest -> ETL pipeline once,
 * plus one intraday observation per fetched coin. */
export function refreshMarketData(): Promise<RefreshMarketDataResult> {
  return apiPost<RefreshMarketDataResult>("/admin/refresh-market-data", {});
}

export type RecoveryStatus = "idle" | "running" | "completed" | "partial_failure" | "failed";

export interface DataRecoveryStatus {
  status: RecoveryStatus;
  last_daily_snapshot_date: string | null;
  expected_latest_daily_date: string | null;
  missing_dates: string[];
  dates_completed: string[];
  current_date_processing: string | null;
  started_at: string | null;
  completed_at: string | null;
  errors: string[];
}

/** GET /admin/data-recovery-status — startup gap-detection/backfill status (Part 13). */
export function getDataRecoveryStatus(): Promise<DataRecoveryStatus> {
  return apiGet<DataRecoveryStatus>("/admin/data-recovery-status");
}
