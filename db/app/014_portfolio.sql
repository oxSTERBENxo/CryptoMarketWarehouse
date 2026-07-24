CREATE TABLE IF NOT EXISTS app.portfolio (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT portfolio_name_not_blank CHECK (btrim(name) <> '')
);

COMMENT ON TABLE app.portfolio IS 'A named collection of cryptocurrency holdings. Application data, not warehouse data.';
