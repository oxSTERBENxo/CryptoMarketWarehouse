-- Redefines analytics.latest_snapshot to be per-coin latest instead of a single global max
-- date_key across the whole fact table. The original definition (008_latest_snapshot.sql)
-- assumed every tracked coin is always loaded together on the same date_key, which held while
-- the live pipeline was the only writer. The historical backfill pipeline
-- (backfill_market_history.py) can legitimately advance a handful of coins to more recent dates
-- than the rest, which under the old global-max definition caused every other coin to vanish
-- from analytics.latest_snapshot (and therefore the dashboard, CoinSelect, and portfolio
-- pricing) the moment any single coin's data got ahead of the pack.
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
    f.market_cap_rank
FROM dw.fact_market_snapshot f
JOIN dw.dim_coin c ON c.coin_key = f.coin_key
JOIN dw.dim_date d ON d.date_key = f.date_key
ORDER BY c.coin_id, f.date_key DESC;

COMMENT ON VIEW analytics.latest_snapshot IS
    'One row per coin as of that coin''s own most recently loaded snapshot date (dates may differ between coins when only some have been historically backfilled ahead of the rest). Foundation view for the other current-state analytical views.';
