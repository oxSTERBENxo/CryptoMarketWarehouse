# ETL Guide

The complete data path: **source → staging → validation → dimensions → facts → analytics views.**
This document walks that path end-to-end and documents the reliability guarantees verified during
this review (both by automated tests and by exercising the pipeline manually against the running
database — see the run transcript in `answers/31-production-readiness-and-polish.md`).

## The path, step by step

1. **Source**: `integrations/coingecko.py` calls the CoinGecko public API and validates the response shape with
   Pydantic (`CoinMarketData`, `CoinHistorySnapshot`, `CoinIntradayObservation`). As of this review,
   these models also reject negative prices/market caps/volumes and non-positive ranks
   (`current_price/market_cap/total_volume/circulating_supply: ge=0`, `market_cap_rank: gt=0`) —
   malformed CoinGecko data is rejected here, before it ever reaches staging.
2. **Staging**: `ingest_market_data.run_ingest` (live) or `backfill_market_history.load_one_day`
   (historical) lands validated rows into `staging.coingecko_market_snapshot` /
   `staging.coingecko_coin_history`, tagged by an `audit.etl_run` row. As of this review, both
   staging tables also carry the same non-negative/positive-rank CHECK constraints at the database
   level (migration `030`), so nothing can bypass the Pydantic validation and land bad data via a
   different code path.
3. **Validation**: shape validation happens at ingestion (Pydantic); value-range validation happens
   at both ingestion (Pydantic) and at the database (CHECK constraints on every table in the path).
   There is no separate row-level data-quality error table — a validation failure raises before the
   row is ever staged, and a whole-batch failure is recorded on `audit.etl_run.error_message` (see
   "Data-quality and failure visibility" below).
4. **Dimensions**: `etl_load_warehouse.upsert_dim_coin` maintains `dw.dim_coin`'s SCD2 history;
   `ensure_dim_date` maintains `dw.dim_date`. See `DATA_WAREHOUSE_MODEL.md` for the full mechanics.
5. **Facts**: `upsert_fact_market_snapshot` / `insert_intraday_from_staging` write the two fact
   tables, both `ON CONFLICT ... DO NOTHING` against a real UNIQUE constraint — see
   "Idempotency" below.
6. **Analytics views**: read-only projections over `dw` (see `ANALYTICS_GUIDE.md`), always current
   as of the last successful fact insert — no separate materialization/refresh step.

## Idempotency: the exact mechanism, verified

- **First run on an empty database**: `select_batch` (auto-pick mode) looks for a `'succeeded'`
  batch with `loaded_at IS NULL`; on an empty database there is none, so `run_etl` returns `None`
  cleanly (`tests/test_etl_load_warehouse.py::test_run_etl_returns_none_when_nothing_to_load`) —
  no exception, no partial state.
- **Repeated run for the same date**: after a batch is loaded, `run_etl` stamps
  `audit.etl_run.loaded_at`, which permanently removes that batch from `select_batch`'s candidate
  set. Verified both at the unit level
  (`test_select_batch_returns_none_when_the_only_batch_is_already_loaded`) and manually against the
  live database during this review: running `etl/ingest_market_data.py` + `etl/load_warehouse.py` twice
  in a row for the same day inserted the staging rows again (staging is intentionally append-only)
  but inserted **zero** new `dw.fact_market_snapshot` rows the second time — confirmed by comparing
  `SELECT count(*) FROM dw.fact_market_snapshot` before and after (unchanged at 1246 rows).
- **Loading several missing dates**: `etl/backfill_market_history.py` pre-checks `fact_exists()` for
  every (coin, date) pair before calling CoinGecko at all, and its staging insert is
  `ON CONFLICT (coin_id, snapshot_date) DO NOTHING` — re-running a backfill over a range that's
  partially already loaded only fetches/inserts what's missing
  (`tests/test_backfill_market_history.py`, e.g. `test_run_backfill_resumes_after_partial_completion`).
- **Duplicate source records**: both fact tables' grain is a real DB `UNIQUE` constraint, and every
  insert path uses `ON CONFLICT ... DO NOTHING` — a duplicate can never land as a second row, in
  any pipeline.
- **Manual snapshot loading**: the "Take New Snapshot" admin action reuses the exact same
  `run_ingest`/`insert_intraday_from_staging` functions as the scheduler — same idempotency
  guarantees, no separate code path to drift out of sync.

## Transaction boundaries and rollback

`run_etl` performs the whole batch (dimension upserts + fact inserts + the `loaded_at` stamp) inside
one `with conn.cursor()` block, committed once at the end. Any exception anywhere in that block
rolls back the entire transaction and records the failure on `audit.etl_run` (status `'failed'`,
`error_message` set) — **a failed load cannot leave a partially-loaded, misleading batch**: either
every staged row's dimension/fact writes land, or none do, and the batch remains eligible for a
future retry since `loaded_at` was never stamped. Verified by
`test_run_etl_rolls_back_and_records_failure_without_marking_batch_loaded`.

`backfill_market_history.load_one_day` commits per (coin, date) pair rather than per whole run —
deliberately, so an interrupted 90-day backfill resumes from wherever it stopped instead of
re-fetching everything.

## Data-quality and failure visibility

- `audit.etl_run` is the run-level audit trail: `pipeline_name`, `status`
  (`running`/`succeeded`/`failed`), `started_at`/`finished_at`, `rows_processed`, `error_message`.
  Every ingest and every warehouse load gets a row here, success or failure.
- There is no per-row data-quality error table (e.g. "row X had a negative price") — as of this
  review that class of bad data is rejected at ingestion/staging (see "Source"/"Staging" above)
  rather than accepted-then-flagged, which is a stronger guarantee for a small, single-source
  pipeline like this one.
- The Warehouse Health page (a developer/operations view at `/warehouse-health`, absent from the
  user navigation — see `answers/31-production-readiness-and-polish.md`) surfaces the
  latest successful/failed run, fact row counts, and missing-date coverage in one place for a quick
  operational check.

## Scheduler-disabled operation

With `ENABLE_SCHEDULER=false` (the default), nothing runs automatically. The warehouse can still be
populated entirely manually: `etl/ingest_market_data.py` → `etl/load_warehouse.py` for a live snapshot,
`etl/backfill_market_history.py --days N` (or explicit `--start-date`/`--end-date`) for historical
gaps, and `python -m etl.ingest_intraday_market_data --coins ...` for intraday observations. `Scheduler.md`
covers the scheduler's own configuration when it is enabled.

## Manual snapshot loading — exact commands used to verify this review

```
python -m database.bootstrap_db        # apply/verify schema (safe to re-run, see below)
python -m etl.ingest_market_data --limit 10
python -m etl.load_warehouse
python -m etl.load_warehouse           # repeat: reports "No new batches to process."
```

## Bootstrap idempotency (schema migrations, not data)

Separately from the ETL data path above, `database/bootstrap_db.py` itself was found to be non-idempotent
before this review: re-running it against an already-migrated database replayed every `*.sql` file
from scratch, and several early `CREATE OR REPLACE VIEW` migrations that a later migration had since
widened failed with `cannot drop columns from view`. Fixed by adding a `public.schema_migrations`
ledger that tracks which files have already been applied (see `database/bootstrap_db.py` and
`tests/test_bootstrap_db.py`); a one-time backfill step recognizes a database that was already fully
migrated before the ledger existed and marks its legacy files as applied without replaying them.
Verified live: bootstrapping the already-migrated development database now backfills 28 legacy
migrations and applies only the genuinely new ones, and a subsequent run reports "no new migrations
to apply."
