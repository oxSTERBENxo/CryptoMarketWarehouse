CREATE OR REPLACE VIEW analytics.top_market_cap AS
SELECT
    row_number() OVER (ORDER BY market_cap_usd DESC NULLS LAST) AS market_cap_position,
    coin_id,
    symbol,
    name,
    snapshot_date,
    market_cap_usd,
    price_usd
FROM analytics.latest_snapshot
ORDER BY market_cap_usd DESC NULLS LAST;

COMMENT ON VIEW analytics.top_market_cap IS
    'Latest snapshot ranked by market cap. Consumers apply their own LIMIT for "top N".';
COMMENT ON COLUMN analytics.top_market_cap.market_cap_position IS
    'Our own computed rank by market cap, distinct from market_cap_rank which is CoinGecko''s own ranking value.';
