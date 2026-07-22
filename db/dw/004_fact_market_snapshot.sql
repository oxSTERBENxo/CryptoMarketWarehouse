CREATE TABLE IF NOT EXISTS dw.fact_market_snapshot (
    fact_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_key INTEGER NOT NULL REFERENCES dw.dim_date (date_key),
    coin_key BIGINT NOT NULL REFERENCES dw.dim_coin (coin_key),

    price_usd NUMERIC(20, 8) NOT NULL,
    market_cap_usd NUMERIC(24, 2),
    volume_24h_usd NUMERIC(24, 2),
    circulating_supply NUMERIC(30, 8),
    market_cap_rank INTEGER,

    dw_loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fact_market_snapshot_grain UNIQUE (date_key, coin_key)
);

CREATE INDEX IF NOT EXISTS fact_market_snapshot_coin_idx ON dw.fact_market_snapshot (coin_key);
CREATE INDEX IF NOT EXISTS fact_market_snapshot_date_idx ON dw.fact_market_snapshot (date_key);

COMMENT ON TABLE dw.fact_market_snapshot IS 'Daily grain: one row per coin per date.';
