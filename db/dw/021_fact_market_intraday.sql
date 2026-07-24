CREATE TABLE IF NOT EXISTS dw.fact_market_intraday (
    intraday_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    coin_key BIGINT NOT NULL REFERENCES dw.dim_coin (coin_key),
    observation_timestamp TIMESTAMPTZ NOT NULL,

    price_usd NUMERIC(20, 8) NOT NULL,
    market_cap_usd NUMERIC(24, 2),
    volume_24h_usd NUMERIC(24, 2),

    source TEXT NOT NULL DEFAULT 'coingecko',
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fact_market_intraday_grain UNIQUE (coin_key, observation_timestamp)
);

CREATE INDEX IF NOT EXISTS fact_market_intraday_coin_idx ON dw.fact_market_intraday (coin_key);
CREATE INDEX IF NOT EXISTS fact_market_intraday_ts_idx ON dw.fact_market_intraday (observation_timestamp);
CREATE INDEX IF NOT EXISTS fact_market_intraday_coin_ts_idx ON dw.fact_market_intraday (coin_key, observation_timestamp);

COMMENT ON TABLE dw.fact_market_intraday IS
    'Sub-daily grain: many rows per coin per day, one per CoinGecko market_chart timestamp. '
    'Deliberately separate from dw.fact_market_snapshot (one row per coin per calendar date) '
    'so the daily warehouse grain is never violated by intraday observations. Not linked to '
    'dw.dim_date, since observation_timestamp is a precise instant, not a calendar day. '
    'Retention: intended to be pruned periodically (e.g. keep the trailing 7 days) since it '
    'exists only to power the "Today" intraday chart, not for long-term trend analysis -- '
    'no automatic retention job is scheduled by default, see ingest_intraday_market_data.py.';
