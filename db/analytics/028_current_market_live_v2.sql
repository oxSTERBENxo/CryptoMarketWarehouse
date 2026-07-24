-- Part 1/2/6: extends analytics.current_market_live (023_current_market_live.sql) with the two
-- fields the main dashboard's live tables and the Buy/Sell/Manual Holdings coin pickers now need:
-- image_url (from dw.dim_coin, since staging never stores it long-term) and
-- price_change_percentage_24h (from staging itself -- a live-only value, see
-- 024_market_snapshot_add_live_fields.sql). Still reads only from the most recent
-- staging.coingecko_market_snapshot run; still never touches dw.fact_market_snapshot.
--
-- Both new columns are appended at the end of the SELECT list: PostgreSQL's CREATE OR REPLACE
-- VIEW only allows adding columns after the existing ones, not inserting them in the middle.
-- analytics_repository.py selects columns by name, so this has no functional effect.
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
    s.ingested_at,
    dc.image_url,
    s.price_change_percentage_24h
FROM staging.coingecko_market_snapshot s
LEFT JOIN dw.dim_coin dc ON dc.coin_id = s.coin_id AND dc.is_current
WHERE s.run_id = (SELECT max(run_id) FROM staging.coingecko_market_snapshot);

COMMENT ON VIEW analytics.current_market_live IS
    'Live current-market values (price/24h change/market cap/volume/rank/logo) from the most recent ingestion run in staging.coingecko_market_snapshot, independent of whether that run has been loaded into dw.fact_market_snapshot yet. Powers the main dashboard''s Take New Snapshot refresh and the Buy/Sell/Manual Holdings coin pickers; analytics.latest_snapshot remains the daily-grain view backing history-dependent features.';
