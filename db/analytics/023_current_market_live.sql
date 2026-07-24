-- Part 8: the main dashboard's "Take New Snapshot" button needs current values (price, market
-- cap, volume, rank) to change on every refresh, even on a same-day repeat press where
-- dw.fact_market_snapshot's (date_key, coin_key) idempotency guard means no new daily row lands.
-- analytics.latest_snapshot (008/019) is unsuitable for that: it's derived from the daily
-- warehouse fact table, so it is frozen until tomorrow's snapshot loads. This view instead reads
-- straight from staging.coingecko_market_snapshot's most recent ingestion run -- the freshest
-- data CoinGecko has given us, regardless of whether the ETL step has (or hasn't) loaded it into
-- the daily fact table yet. Never touches dw.fact_market_snapshot, so the daily historical grain
-- stays exactly as append-safe/idempotent as before.
CREATE OR REPLACE VIEW analytics.current_market_live AS
SELECT
    s.coin_id,
    s.symbol,
    s.name,
    s.current_price AS price_usd,
    s.market_cap AS market_cap_usd,
    s.total_volume AS volume_24h_usd,
    s.circulating_supply,
    s.market_cap_rank,
    s.ingested_at
FROM staging.coingecko_market_snapshot s
WHERE s.run_id = (SELECT max(run_id) FROM staging.coingecko_market_snapshot);

COMMENT ON VIEW analytics.current_market_live IS
    'Live current-market values (price/market cap/volume/rank) from the most recent ingestion run in staging.coingecko_market_snapshot, independent of whether that run has been loaded into dw.fact_market_snapshot yet. Powers the main dashboard''s Take New Snapshot refresh; analytics.latest_snapshot remains the daily-grain view backing history-dependent features.';
