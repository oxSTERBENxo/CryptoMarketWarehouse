CREATE OR REPLACE VIEW analytics.market_intraday AS
SELECT
    c.coin_id,
    c.symbol,
    c.name,
    f.observation_timestamp,
    f.price_usd,
    f.market_cap_usd,
    f.volume_24h_usd
FROM dw.fact_market_intraday f
JOIN dw.dim_coin c ON c.coin_key = f.coin_key
ORDER BY f.observation_timestamp, c.coin_id;

COMMENT ON VIEW analytics.market_intraday IS
    'Sub-daily time series from dw.fact_market_intraday, joined to current coin attributes. '
    'Distinct from analytics.market_history (daily grain) -- powers the Coin Details "Today" chart.';
