-- Part 2: one consistent backend field (image_url) for coin logos everywhere, instead of
-- hardcoding image URLs per frontend component. Modeled as a dw.dim_coin attribute (like
-- symbol/name) so every analytics view that already joins dim_coin gets it for free.
--
-- Deliberately NOT part of the SCD2 change-detection in etl_load_warehouse.upsert_dim_coin: a
-- logo refresh is cosmetic, not an identity change, so it's kept up to date via a plain in-place
-- UPDATE on the current row rather than minting a new dim_coin version. See upsert_dim_coin.
ALTER TABLE dw.dim_coin
    ADD COLUMN IF NOT EXISTS image_url TEXT;

COMMENT ON COLUMN dw.dim_coin.image_url IS 'CoinGecko-hosted coin logo URL. Updated in place (not SCD2-versioned) whenever the live ingestion pipeline supplies a new value; historical backfill never supplies one and never clears an existing value.';
