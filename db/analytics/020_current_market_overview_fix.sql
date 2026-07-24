-- Companion fix to 019_latest_snapshot_per_coin.sql: now that analytics.latest_snapshot can
-- contain more than one distinct snapshot_date (each coin's own latest), the original
-- `GROUP BY snapshot_date` here would silently split the overview into multiple rows instead of
-- the single aggregate row analytics_repository.fetch_overview()/MarketOverview expect
-- (`cur.fetchone()`), and would under-count coins/market cap by only summing whichever group
-- happened to be picked. Aggregate across the whole view instead, reporting the most recent
-- snapshot_date seen (a coin_count of every currently-tracked coin, not just the newest cohort).
CREATE OR REPLACE VIEW analytics.current_market_overview AS
SELECT
    max(snapshot_date) AS snapshot_date,
    count(*) AS coin_count,
    sum(market_cap_usd) AS total_market_cap_usd,
    sum(volume_24h_usd) AS total_volume_24h_usd
FROM analytics.latest_snapshot;

COMMENT ON VIEW analytics.current_market_overview IS
    'Single-row aggregate summary across every coin''s latest snapshot: coin count, total market cap, total 24h volume, and the most recent snapshot_date among them.';
