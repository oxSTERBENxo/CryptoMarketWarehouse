-- Part 19: no CHECK constraint anywhere in the warehouse ever guarded against a negative price,
-- market cap, volume, supply, or rank -- only NOT NULL on price_usd existed (confirmed by grepping
-- every db/*.sql file for CHECK before this migration). CoinGecko has never been observed to send
-- negative values, but nothing stopped one from landing here if it ever did. Uses a guarded DO
-- block (idempotent add-if-missing) rather than a bare ALTER TABLE ADD CONSTRAINT, because
-- bootstrap_db.py replays every *.sql file on every run and Postgres has no
-- "ADD CONSTRAINT IF NOT EXISTS" syntax.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fact_market_snapshot_metrics_nonnegative'
    ) THEN
        ALTER TABLE dw.fact_market_snapshot
            ADD CONSTRAINT fact_market_snapshot_metrics_nonnegative CHECK (
                price_usd >= 0
                AND (market_cap_usd IS NULL OR market_cap_usd >= 0)
                AND (volume_24h_usd IS NULL OR volume_24h_usd >= 0)
                AND (circulating_supply IS NULL OR circulating_supply >= 0)
                AND (market_cap_rank IS NULL OR market_cap_rank > 0)
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fact_market_intraday_metrics_nonnegative'
    ) THEN
        ALTER TABLE dw.fact_market_intraday
            ADD CONSTRAINT fact_market_intraday_metrics_nonnegative CHECK (
                price_usd >= 0
                AND (market_cap_usd IS NULL OR market_cap_usd >= 0)
                AND (volume_24h_usd IS NULL OR volume_24h_usd >= 0)
            );
    END IF;
END $$;
