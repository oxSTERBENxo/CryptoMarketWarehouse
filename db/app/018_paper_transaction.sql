CREATE TABLE IF NOT EXISTS app.paper_transaction (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES app.paper_account (id) ON DELETE CASCADE,

    -- Business key into the warehouse (dw.dim_coin.symbol), same pattern as
    -- app.portfolio_holding.coin_symbol: survives independently of warehouse SCD2 churn.
    coin_symbol TEXT NOT NULL,

    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('BUY', 'SELL')),
    quantity NUMERIC(30, 8) NOT NULL CHECK (quantity > 0),
    execution_price NUMERIC(20, 8) NOT NULL CHECK (execution_price >= 0),
    total_value NUMERIC(20, 2) NOT NULL,

    -- Only set for SELL rows: (execution_price - weighted_avg_cost_at_time_of_sale) * quantity.
    -- Computed once at execution time and never rewritten afterwards, so past transactions stay
    -- an immutable, auditable record even as later trades change the current average cost.
    realized_profit NUMERIC(20, 2),

    executed_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT paper_transaction_symbol_not_blank CHECK (btrim(coin_symbol) <> ''),
    CONSTRAINT paper_transaction_realized_profit_only_on_sell
        CHECK (transaction_type = 'SELL' OR realized_profit IS NULL)
);

CREATE INDEX IF NOT EXISTS paper_transaction_account_idx
    ON app.paper_transaction (account_id, executed_at);

COMMENT ON TABLE app.paper_transaction IS
    'Immutable, append-only paper-trading ledger. Current holdings and weighted-average cost are derived by replaying these rows in paper_trading_service, never stored redundantly.';
