-- Part 19 (companion to db/dw/029_fact_metric_value_constraints.sql): apply the same
-- non-negative/positive-rank guard to the staging layer, so bad values are rejected at the very
-- first landing point rather than only at the warehouse fact tables.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'coingecko_market_snapshot_metrics_nonnegative'
    ) THEN
        ALTER TABLE staging.coingecko_market_snapshot
            ADD CONSTRAINT coingecko_market_snapshot_metrics_nonnegative CHECK (
                current_price >= 0
                AND (market_cap IS NULL OR market_cap >= 0)
                AND (total_volume IS NULL OR total_volume >= 0)
                AND (circulating_supply IS NULL OR circulating_supply >= 0)
                AND (market_cap_rank IS NULL OR market_cap_rank > 0)
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'coingecko_coin_history_metrics_nonnegative'
    ) THEN
        ALTER TABLE staging.coingecko_coin_history
            ADD CONSTRAINT coingecko_coin_history_metrics_nonnegative CHECK (
                current_price >= 0
                AND (market_cap IS NULL OR market_cap >= 0)
                AND (total_volume IS NULL OR total_volume >= 0)
                AND (circulating_supply IS NULL OR circulating_supply >= 0)
                AND (market_cap_rank IS NULL OR market_cap_rank > 0)
            );
    END IF;
END $$;
