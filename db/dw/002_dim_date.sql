CREATE TABLE IF NOT EXISTS dw.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year SMALLINT NOT NULL,
    quarter SMALLINT NOT NULL,
    month SMALLINT NOT NULL,
    month_name TEXT NOT NULL,
    day SMALLINT NOT NULL,
    day_of_week SMALLINT NOT NULL,
    day_name TEXT NOT NULL,
    week_of_year SMALLINT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

COMMENT ON TABLE dw.dim_date IS 'One row per calendar date.';
COMMENT ON COLUMN dw.dim_date.date_key IS 'Surrogate key in YYYYMMDD form, one-to-one with full_date.';
