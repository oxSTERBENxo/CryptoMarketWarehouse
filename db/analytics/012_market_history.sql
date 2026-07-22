CREATE OR REPLACE VIEW analytics.market_history AS
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
ORDER BY d.full_date, c.coin_id;

COMMENT ON VIEW analytics.market_history IS
    'Full historical time series: every fact row joined to the coin attributes that were current when it was loaded (SCD2-correct), for trend analysis over time.';
