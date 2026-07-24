-- Part 6: CoinGecko's /coins/markets response already includes a logo URL and a 24h percentage
-- change, but staging.coingecko_market_snapshot never captured either. Both are live-only values
-- (the historical /coins/{id}/history endpoint used by backfill_market_history.py reports
-- neither), so they land here -- the live ingestion staging table -- rather than
-- staging.coingecko_coin_history.
ALTER TABLE staging.coingecko_market_snapshot
    ADD COLUMN IF NOT EXISTS image_url TEXT,
    ADD COLUMN IF NOT EXISTS price_change_percentage_24h NUMERIC;

COMMENT ON COLUMN staging.coingecko_market_snapshot.image_url IS 'CoinGecko-hosted coin logo URL, as returned by /coins/markets.';
COMMENT ON COLUMN staging.coingecko_market_snapshot.price_change_percentage_24h IS '24h price change percentage as reported directly by CoinGecko /coins/markets -- never estimated from intraday rows.';
