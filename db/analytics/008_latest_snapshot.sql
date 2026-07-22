CREATE OR REPLACE VIEW analytics.latest_snapshot AS
SELECT
    c.coin_id,
    c.symbol,
    c.name,
    d.full_date AS snapshot_date,
    f.price_usd,
    f.market_cap_usd,
    f.volume_24h_usd,
    f.circulating_supply,
    f.market_cap_rank
FROM dw.fact_market_snapshot f
JOIN dw.dim_coin c ON c.coin_key = f.coin_key
JOIN dw.dim_date d ON d.date_key = f.date_key
WHERE f.date_key = (SELECT max(date_key) FROM dw.fact_market_snapshot);

COMMENT ON VIEW analytics.latest_snapshot IS
    'One row per coin as of the most recently loaded snapshot date. Foundation view for the other current-state analytical views.';
