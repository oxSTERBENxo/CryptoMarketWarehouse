CREATE OR REPLACE VIEW analytics.current_market_overview AS
SELECT
    snapshot_date,
    count(*) AS coin_count,
    sum(market_cap_usd) AS total_market_cap_usd,
    sum(volume_24h_usd) AS total_volume_24h_usd
FROM analytics.latest_snapshot
GROUP BY snapshot_date;

COMMENT ON VIEW analytics.current_market_overview IS
    'Single-row aggregate summary of the latest snapshot: coin count, total market cap, total 24h volume.';
