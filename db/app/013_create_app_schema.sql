CREATE SCHEMA IF NOT EXISTS app;

COMMENT ON SCHEMA app IS
    'Application-owned data (e.g. user portfolios) that references warehouse data by business key but is not itself part of the warehouse. Never written to by staging/ETL.';
