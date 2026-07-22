# Milestone: Staging Layer

## Design

`staging.coingecko_market_snapshot` — one row per coin per ingestion run, columns kept close to `coingecko.py`'s `CoinMarketData` model (that model is "the CoinGecko response" as our system knows it; not bypassing the client to reach raw JSON, since that would duplicate HTTP logic outside it).

| Column | Why |
|---|---|
| `staging_id` | Surrogate PK for the staging row; staging doesn't need a business key. |
| `run_id` | Batch identifier — references `audit.etl_run.run_id`, reusing the audit table already built in the DW milestone instead of inventing a parallel concept. |
| `source` | Defaults to `'coingecko'`; room for a second provider later without new tables. |
| `ingested_at` | Per-row landing timestamp, distinct from the batch's own `started_at`. |
| `coin_id`/`symbol`/`name` | Identity fields, unmodified. |
| `current_price`/`market_cap`/`market_cap_rank`/`total_volume`/`circulating_supply` | Measures, stored as plain `NUMERIC` (no precision/scale limits) — staging preserves fidelity, precision decisions belong to the not-yet-built ETL step. |

**Duplicate executions:** staging is intentionally append-only — a rerun is expected to happen repeatedly and should produce a new `run_id`/batch, not fail. What matters is that a *failed* run leaves zero partial rows (one transaction per batch) and that `audit.etl_run` always reflects `succeeded`/`failed` accurately, so downstream ETL can filter on run status. Deduplication of coin data itself belongs to the (out-of-scope) warehouse ETL layer.

## Files created / modified

| File | Purpose |
|---|---|
| `db/staging/006_coingecko_market_snapshot.sql` | Creates the staging table + index on `run_id`, idempotent (`IF NOT EXISTS`), picked up automatically by `bootstrap_db.py`'s numeric-order discovery. |
| `staging_repository.py` | New. Single responsibility: `insert_market_snapshots(conn, run_id, coins)` — the only place that writes to the staging table. |
| `ingest_market_data.py` | New. The ingestion script: starts an `audit.etl_run` row, calls the CoinGecko client, inserts staging rows transactionally, finalizes the run row. |
| `README.md` | Added the ingestion command and bootstrap note about the new staging table. |

`coingecko.py` was **not modified** — it has no database imports, keeping it fully independent as required.

## Ingestion flow: API to staging

1. `ingest_market_data.py` opens a connection (`database.get_connection()`) and inserts an `audit.etl_run` row with `status='running'`, committing immediately so the run is visible even if a later step fails. This yields `run_id`.
2. Calls `coingecko.fetch_top_markets(...)` — pure API client, returns typed `CoinMarketData` objects or raises `CoinGeckoAPIError`.
3. On API failure: `audit.etl_run` is updated to `status='failed'` with the error message, script exits `1`. No staging rows are touched.
4. On API success: `staging_repository.insert_market_snapshots(conn, run_id, coins)` batch-inserts all rows in one transaction; on any DB error the transaction is rolled back, the run is marked `failed`, script exits `1`.
5. On success, the transaction is committed, `audit.etl_run` is updated to `status='succeeded'` with `rows_processed`, and the script prints a summary and exits `0`.

## Live verification

- `bootstrap_db.py` re-run picked up the new `006_coingecko_market_snapshot.sql` automatically and applied it (`OK`, exit 0).
- `ingest_market_data.py --limit 20` against the live CoinGecko API: **inserted 20 rows**, `run_id=1` marked `succeeded` with `rows_processed=20`.
- Verified directly in Postgres: 5 sample rows correctly linked to `run_id=1` with real prices (Bitcoin `$65839`, Ethereum `$1923.61`, etc.), `staging_row_count = 20`.
- Re-ran the script a second time (duplicate execution test): created `run_id=2`, inserted another 20 rows cleanly — `staging.coingecko_market_snapshot` now has 40 rows total (20 + 20), split correctly by `run_id`, both `audit.etl_run` rows show `succeeded`. No conflicts, no corruption.

## Rows inserted into PostgreSQL

- Run 1: 20 rows
- Run 2 (duplicate-execution test): 20 rows
- **Total in `staging.coingecko_market_snapshot`: 40 rows**
