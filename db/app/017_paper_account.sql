CREATE TABLE IF NOT EXISTS app.paper_account (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    initial_cash NUMERIC(20, 2) NOT NULL CHECK (initial_cash >= 0),
    cash_balance NUMERIC(20, 2) NOT NULL CHECK (cash_balance >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT paper_account_name_not_blank CHECK (btrim(name) <> '')
);

COMMENT ON TABLE app.paper_account IS
    'A simulated (paper) trading account: starting cash plus a live cash balance. No real money. One default account is created lazily by the API on first access.';
