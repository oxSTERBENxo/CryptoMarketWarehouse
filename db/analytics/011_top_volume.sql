CREATE OR REPLACE VIEW analytics.top_volume AS
SELECT
    row_number() OVER (ORDER BY volume_24h_usd DESC NULLS LAST) AS volume_position,
    coin_id,
    symbol,
    name,
    snapshot_date,
    volume_24h_usd,
    price_usd
FROM analytics.latest_snapshot
ORDER BY volume_24h_usd DESC NULLS LAST;

COMMENT ON VIEW analytics.top_volume IS
    'Latest snapshot ranked by 24h volume. Consumers apply their own LIMIT for "top N".';
COMMENT ON COLUMN analytics.top_volume.volume_position IS
    'Our own computed rank by 24h volume, independent of market cap ranking.';
