CREATE TABLE IF NOT EXISTS app.portfolio_holding (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    portfolio_id BIGINT NOT NULL REFERENCES app.portfolio (id) ON DELETE CASCADE,

    -- Business key into the warehouse (dw.dim_coin.symbol), not a foreign key: holdings must
    -- survive independently of warehouse SCD2 churn, and the warehouse is never written to
    -- from here. Current price/name are resolved at read time via analytics views.
    coin_symbol TEXT NOT NULL,

    quantity NUMERIC(30, 8) NOT NULL,
    average_buy_price NUMERIC(20, 8) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT portfolio_holding_symbol_not_blank CHECK (btrim(coin_symbol) <> ''),
    CONSTRAINT portfolio_holding_quantity_positive CHECK (quantity > 0),
    CONSTRAINT portfolio_holding_avg_price_nonnegative CHECK (average_buy_price >= 0),
    CONSTRAINT portfolio_holding_unique_symbol_per_portfolio UNIQUE (portfolio_id, coin_symbol)
);

CREATE INDEX IF NOT EXISTS portfolio_holding_portfolio_idx ON app.portfolio_holding (portfolio_id);

COMMENT ON TABLE app.portfolio_holding IS
    'One row per coin held in a portfolio. Cascade-deleted with its parent portfolio. Does not duplicate market data — only the user-entered quantity and average buy price.';
COMMENT ON COLUMN app.portfolio_holding.coin_symbol IS 'Business key matching dw.dim_coin.symbol, matched case-insensitively at read time; stored uppercased.';
