CREATE TABLE IF NOT EXISTS staging.coingecko_coin_history (
    staging_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES audit.etl_run (run_id),
    source TEXT NOT NULL DEFAULT 'coingecko',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    coin_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    current_price NUMERIC NOT NULL,
    market_cap NUMERIC,
    total_volume NUMERIC,
    market_cap_rank INTEGER,
    circulating_supply NUMERIC,

    CONSTRAINT coingecko_coin_history_unique UNIQUE (coin_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS coingecko_coin_history_run_idx
    ON staging.coingecko_coin_history (run_id);

COMMENT ON TABLE staging.coingecko_coin_history IS
    'Raw CoinGecko historical (per-day) market data landed as-is by the backfill pipeline, one row per coin per calendar date. Append-only, unlike live ingestion this carries an explicit snapshot_date since backfilled rows are never "today".';
