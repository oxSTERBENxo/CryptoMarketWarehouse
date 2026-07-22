CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS analytics;

COMMENT ON SCHEMA staging IS 'Landing zone for raw ingested data (tables added in a future milestone).';
COMMENT ON SCHEMA dw IS 'Dimensional data warehouse (star schema).';
COMMENT ON SCHEMA audit IS 'Operational metadata about pipeline runs.';
COMMENT ON SCHEMA analytics IS 'Reusable read-only analytical views over dw, for future APIs and dashboards to consume.';
