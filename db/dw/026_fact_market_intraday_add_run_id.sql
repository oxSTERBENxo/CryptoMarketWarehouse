-- Part 10/18: lets a manual "Take New Snapshot" press's intraday rows be traced back to the
-- exact staging ingestion run that produced them, so it's possible to verify "one button press ==
-- one distinct intraday run" without changing the existing (coin_key, observation_timestamp)
-- uniqueness grain (fact_market_intraday_grain, in 021_fact_market_intraday.sql), which already
-- satisfies the "not just (date_key, coin_key)" requirement. Nullable: rows loaded by the
-- pre-existing ingest_intraday_market_data.py job (a separate, curated-coin-list job with no
-- staging run of its own) simply leave it NULL.
ALTER TABLE dw.fact_market_intraday
    ADD COLUMN IF NOT EXISTS run_id BIGINT REFERENCES audit.etl_run (run_id);

CREATE INDEX IF NOT EXISTS fact_market_intraday_run_idx ON dw.fact_market_intraday (run_id);

COMMENT ON COLUMN dw.fact_market_intraday.run_id IS 'The staging.coingecko_market_snapshot ingestion run (audit.etl_run.run_id) this intraday observation was derived from, when known. NULL for rows loaded by ingest_intraday_market_data.py, which has no single staging run per coin.';
