ALTER TABLE audit.etl_run ADD COLUMN IF NOT EXISTS loaded_at TIMESTAMPTZ;

COMMENT ON COLUMN audit.etl_run.loaded_at IS 'Set when this ingestion batch has been loaded into the warehouse, so it is not picked up again by the ETL.';
