# Milestone: First ETL — Staging to Warehouse

## ETL flow

`etl_load_warehouse.py`:
1. Selects one staging batch — explicit `--run-id`, or (default) the oldest `audit.etl_run` row with `pipeline_name='coingecko_market_snapshot'`, `status='succeeded'`, `loaded_at IS NULL`.
2. Derives the snapshot date from that batch's `started_at` (one ingestion run = one day's snapshot).
3. Ensures `dw.dim_date` has a row for that date.
4. For every staged coin: upserts `dw.dim_coin` (SCD2), then upserts `dw.fact_market_snapshot` for `(date_key, coin_key)`.
5. Marks the batch's `audit.etl_run` row with `loaded_at = now()`.
6. Steps 3–5 all happen inside one transaction.
7. The ETL's own execution is logged as its own `audit.etl_run` row (`pipeline_name='coingecko_warehouse_load'`).

## SCD2 logic for `dim_coin`

Per staged coin, look up the current row (`is_current=true`) by `coin_id`:
- No current row → insert new (**inserted**).
- Current row exists, attributes unchanged → no-op (this is what makes reruns idempotent on the dimension side).
- Current row exists, attributes changed → close old row (`valid_to=now()`, `is_current=false`), insert new current row (**updated** + inserted).

The fact row always links to whichever `coin_key` is current after this step.

## Preventing duplicate/accidental reloads

Two layers: (1) `audit.etl_run.loaded_at` (new column) marks a batch consumed — default selection skips loaded batches, preventing *accidental* reprocessing; (2) true idempotency comes from the data model itself — `fact_market_snapshot` uses `INSERT ... ON CONFLICT (date_key, coin_key) DO NOTHING`, and `dim_coin`'s SCD2 upsert compares against current state, not batch history — so even an explicit forced reprocess can't create duplicates.

## Files created / modified

| File | Purpose |
|---|---|
| `db/audit/007_etl_run_add_loaded_at.sql` | Adds nullable `loaded_at` column to `audit.etl_run`, idempotent (`ADD COLUMN IF NOT EXISTS`). |
| `etl_load_warehouse.py` | New. The ETL script: batch selection, `dim_date`/`dim_coin`/`fact_market_snapshot` upserts in one transaction, batch marking, run logging, summary output. |
| `README.md` | Added the `etl_load_warehouse.py` command. |

## Complete flow: staging to warehouse

`ingest_market_data.py` (previous milestone) writes rows to `staging.coingecko_market_snapshot` tagged with a `run_id`, and records that run in `audit.etl_run` (`pipeline_name='coingecko_market_snapshot'`). `etl_load_warehouse.py` reads one such run's staged rows, resolves/creates the `dim_date` row for that day, resolves/creates-or-versions the `dim_coin` row for each coin (SCD2), and inserts the corresponding `fact_market_snapshot` row per coin — all as one transaction — then stamps the source batch as loaded and logs its own run.

## Live verification

**First run** (`etl_load_warehouse.py`, auto-selected batch 1, 20 staged coins):
```
Batch processed: staging run_id=1 (snapshot date 2026-07-22)
  dim_date rows inserted:       1
  dim_coin rows inserted:       20
  dim_coin rows updated (SCD2): 0
  fact rows inserted:           20
```
Verified directly in Postgres: `dw.dim_date`=1 row, `dw.dim_coin`=20 rows (all current), `dw.fact_market_snapshot`=20 rows, `audit.etl_run` run_id=1 marked `loaded_at` set.

**Second run, no args** (auto-selected batch 2 — a *different* batch, same day/coins): 0 new rows across every table (dim_date already existed, dim_coin attributes unchanged, fact rows already present for that date/coin) — demonstrates the grain constraint holds even across genuinely different batches.

**Third run, `--run-id 1`** (explicit reprocess of the *same* already-loaded batch): 0 new rows across every table — direct proof of idempotency on forced reprocessing.

**Fourth run, no args** (nothing left unloaded): `No new batches to process.`, exit code 0.

**Final counts after 4 ETL invocations across 2 staging batches:** `dw.dim_date`=1, `dw.dim_coin`=20, `dw.fact_market_snapshot`=20 — unchanged from after the very first run. No duplicates at any point.

## Row counts

- Inserted dimension rows: 1 `dim_date` row + 20 `dim_coin` rows = **21**
- Inserted fact rows: **20**
