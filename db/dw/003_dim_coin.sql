CREATE TABLE IF NOT EXISTS dw.dim_coin (
    coin_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    coin_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to TIMESTAMPTZ,
    is_current BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT dim_coin_valid_range CHECK (valid_to IS NULL OR valid_to > valid_from)
);

-- SCD2 invariant: at most one current row per coin at any time.
CREATE UNIQUE INDEX IF NOT EXISTS dim_coin_current_uidx
    ON dw.dim_coin (coin_id)
    WHERE is_current;

COMMENT ON TABLE dw.dim_coin IS 'SCD Type 2 dimension: one row per coin attribute version, referenced by surrogate key coin_key.';
COMMENT ON COLUMN dw.dim_coin.coin_id IS 'Business key from the source system (e.g. CoinGecko coin id).';
