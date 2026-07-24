-- Part 2/6: surface dw.dim_coin.image_url (025_dim_coin_add_image_url.sql) through every
-- analytics view that already joins dim_coin, so every table/picker in the frontend can render a
-- logo from the same one field without a separate lookup. Otherwise identical to the prior
-- definitions (019_latest_snapshot_per_coin.sql, 010_top_market_cap.sql, 011_top_volume.sql,
-- 012_market_history.sql, 022_market_intraday.sql).
--
-- image_url is appended as the LAST column in every SELECT list (rather than grouped next to
-- name/symbol) because PostgreSQL's CREATE OR REPLACE VIEW only allows adding columns at the end
-- of an existing view's column list, not inserting them in the middle. Column order has no
-- semantic meaning here: analytics_repository.py always selects columns by name.
CREATE OR REPLACE VIEW analytics.latest_snapshot AS
SELECT DISTINCT ON (c.coin_id)
    c.coin_id,
    c.symbol,
    c.name,
    d.full_date AS snapshot_date,
    f.price_usd,
    f.market_cap_usd,
    f.volume_24h_usd,
    f.circulating_supply,
    f.market_cap_rank,
    c.image_url
FROM dw.fact_market_snapshot f
JOIN dw.dim_coin c ON c.coin_key = f.coin_key
JOIN dw.dim_date d ON d.date_key = f.date_key
ORDER BY c.coin_id, f.date_key DESC;

COMMENT ON VIEW analytics.latest_snapshot IS
    'One row per coin as of that coin''s own most recently loaded snapshot date (dates may differ between coins when only some have been historically backfilled ahead of the rest). Foundation view for the other current-state analytical views.';

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
    f.market_cap_rank,
    c.image_url
FROM dw.fact_market_snapshot f
JOIN dw.dim_coin c ON c.coin_key = f.coin_key
JOIN dw.dim_date d ON d.date_key = f.date_key
ORDER BY d.full_date, c.coin_id;

COMMENT ON VIEW analytics.market_history IS
    'Full historical time series: every fact row joined to the coin attributes that were current when it was loaded (SCD2-correct), for trend analysis over time.';

CREATE OR REPLACE VIEW analytics.top_market_cap AS
SELECT
    row_number() OVER (ORDER BY market_cap_usd DESC NULLS LAST) AS market_cap_position,
    coin_id,
    symbol,
    name,
    snapshot_date,
    market_cap_usd,
    price_usd,
    image_url
FROM analytics.latest_snapshot
ORDER BY market_cap_usd DESC NULLS LAST;

COMMENT ON VIEW analytics.top_market_cap IS
    'Latest snapshot ranked by market cap. Consumers apply their own LIMIT for "top N".';
COMMENT ON COLUMN analytics.top_market_cap.market_cap_position IS
    'Our own computed rank by market cap, distinct from market_cap_rank which is CoinGecko''s own ranking value.';

CREATE OR REPLACE VIEW analytics.top_volume AS
SELECT
    row_number() OVER (ORDER BY volume_24h_usd DESC NULLS LAST) AS volume_position,
    coin_id,
    symbol,
    name,
    snapshot_date,
    volume_24h_usd,
    price_usd,
    image_url
FROM analytics.latest_snapshot
ORDER BY volume_24h_usd DESC NULLS LAST;

COMMENT ON VIEW analytics.top_volume IS
    'Latest snapshot ranked by 24h volume. Consumers apply their own LIMIT for "top N".';
COMMENT ON COLUMN analytics.top_volume.volume_position IS
    'Our own computed rank by 24h volume, independent of market cap ranking.';

CREATE OR REPLACE VIEW analytics.market_intraday AS
SELECT
    c.coin_id,
    c.symbol,
    c.name,
    f.observation_timestamp,
    f.price_usd,
    f.market_cap_usd,
    f.volume_24h_usd,
    c.image_url
FROM dw.fact_market_intraday f
JOIN dw.dim_coin c ON c.coin_key = f.coin_key
ORDER BY f.observation_timestamp, c.coin_id;

COMMENT ON VIEW analytics.market_intraday IS
    'Sub-daily time series from dw.fact_market_intraday, joined to current coin attributes. '
    'Distinct from analytics.market_history (daily grain) -- powers the Coin Details "Today" chart.';
