CREATE TABLE IF NOT EXISTS staging.coingecko_market_snapshot (
    staging_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES audit.etl_run (run_id),
    source TEXT NOT NULL DEFAULT 'coingecko',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    coin_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    current_price NUMERIC NOT NULL,
    market_cap NUMERIC,
    market_cap_rank INTEGER,
    total_volume NUMERIC,
    circulating_supply NUMERIC
);

CREATE INDEX IF NOT EXISTS coingecko_market_snapshot_run_idx
    ON staging.coingecko_market_snapshot (run_id);

COMMENT ON TABLE staging.coingecko_market_snapshot IS 'Raw CoinGecko market data landed as-is, one row per coin per ingestion run. Append-only.';
