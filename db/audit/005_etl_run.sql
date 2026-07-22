CREATE TABLE IF NOT EXISTS audit.etl_run (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'succeeded', 'failed')),
    rows_processed INTEGER,
    error_message TEXT,

    CONSTRAINT etl_run_finished_after_started CHECK (finished_at IS NULL OR finished_at >= started_at)
);

COMMENT ON TABLE audit.etl_run IS 'One row per pipeline execution, for operational tracking of future ETL runs.';
