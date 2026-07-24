# Data Warehouse Model

This document describes the warehouse's dimensional model: every dimension and fact table's grain,
the SCD Type 2 mechanics of `dim_coin`, the staging layer, incremental-load gating, and data-quality
guarantees. It reflects the schema as of this review (migrations `001`–`030`, see `db/`).

## Schemas

| Schema | Purpose |
|---|---|
| `staging` | Raw, append-only landing zone for CoinGecko API responses, tagged by ingestion run. Never queried directly by the API except for `analytics.current_market_live` (see below). |
| `dw` | The dimensional warehouse: dimensions and facts, at their declared grain, loaded from staging. |
| `analytics` | Read-only views over `dw` (and, for one view, `staging`) shaped for the application's queries. Nothing writes to `analytics`. |
| `audit` | `etl_run`: one row per pipeline invocation (ingest or warehouse-load), its status, and any error. The only run-level data-quality/error record in the system. |
| `app` | Application data unrelated to the warehouse proper: manual-holdings portfolios and paper-trading accounts/transactions. |

## Dimensions

### `dw.dim_date`
One row per calendar date, `date_key` as `YYYYMMDD` integer surrogate key. Static, inserted
on-demand by `etl_load_warehouse.ensure_dim_date` the first time a load needs a date that isn't
present yet.

### `dw.dim_coin` — SCD Type 2
One row per **version** of a coin's attributes (`symbol`, `name`), surrogate-keyed by `coin_key`.
- `valid_from` / `valid_to` / `is_current` track each version's validity window; `valid_to IS NULL`
  means "still current."
- `CHECK (valid_to IS NULL OR valid_to > valid_from)` rejects a zero/negative-length version.
- `CREATE UNIQUE INDEX ... ON dw.dim_coin (coin_id) WHERE is_current` is the SCD2 invariant: **at
  most one current row per `coin_id` at any time**, enforced by Postgres itself, not just
  application logic.
- A symbol/name change closes the current row (`valid_to = now(), is_current = false`) and inserts
  a new one, inside the same transaction as the fact insert that triggered it
  (`etl_load_warehouse.upsert_dim_coin`).
- `image_url` (added later) is **not** SCD2-versioned — it's updated in place on the current row,
  by design (a logo change isn't a meaningful "new version" for analytical purposes, and versioning
  it would multiply dimension rows for a purely cosmetic field).

**Known, accepted gaps** (documented here rather than "fixed" with speculative engineering, since
neither has ever been observed in practice and both are already mitigated):
- No exclusion constraint prevents overlapping `[valid_from, valid_to)` ranges among *historical*
  (non-current) rows for the same coin — only the "one current row" invariant is DB-enforced. A bug
  that produced two historical rows with overlapping ranges wouldn't be caught.
- `upsert_dim_coin`'s read-then-write (`SELECT` current row, then `UPDATE`/`INSERT`) has no
  `SELECT ... FOR UPDATE` row lock, so two *separate processes* racing to update the same coin_id
  simultaneously could interleave. In-process concurrency is already serialized by
  `pipeline_runner._run_lock`; only a multi-host deployment (out of scope — see
  `KNOWN_LIMITATIONS.md`) could hit this.

## Facts

### `dw.fact_market_snapshot` — daily grain
**One row per coin per calendar date.** `UNIQUE (date_key, coin_key)` is the grain constraint —
enforced by Postgres, not just "how the loader happens to behave." Every insert
(`etl_load_warehouse.upsert_fact_market_snapshot`, and `backfill_market_history`'s reuse of it) is
`INSERT ... ON CONFLICT (date_key, coin_key) DO NOTHING`, so re-running the ETL or backfill for a
date/coin that's already loaded is a safe no-op, never a duplicate.

As of this review, `CHECK (price_usd >= 0 AND market_cap_usd/volume_24h_usd/circulating_supply IS
NULL OR >= 0 AND market_cap_rank IS NULL OR > 0)` (migration `029`) rejects negative/invalid metric
values at the database level, on top of the pre-existing `NOT NULL` on `price_usd`.

### `dw.fact_market_intraday` — sub-daily grain
**Many rows per coin per calendar date, one per CoinGecko `market_chart` observation timestamp.**
`UNIQUE (coin_key, observation_timestamp)` is the grain constraint. Deliberately a **separate**
fact table from `fact_market_snapshot`, not a finer-grained partition of it, so the daily grain is
never at risk of being violated by sub-daily rows — and deliberately **not** linked to `dw.dim_date`
(an `observation_timestamp` is a precise instant, not a calendar day). Powers only the Coin Details
"Today" intraday chart, not long-term trend analysis (that's `fact_market_snapshot`'s job).

Retention: intended to hold only a rolling recent window, since it exists purely for the "Today"
chart. Pruned by `ingest_intraday_market_data.prune_old_intraday` (default 2-day retention), called
both by the standalone intraday CLI job and — as of this review — by `pipeline_runner`'s "Take New
Snapshot" path too (previously that manual path never pruned, so a warehouse relying on it alone
would have grown this table unboundedly).

Same `029` migration adds the non-negative CHECK here too.

## Staging

### `staging.coingecko_market_snapshot`
Raw landing zone for the **live** ingestion pipeline (`etl/ingest_market_data.py`), one row per coin per
ingestion run, tagged by `run_id` (`audit.etl_run`). Append-only — reruns simply land a new batch
under a new `run_id`; there's no unique constraint here because each batch is scoped by its own
`run_id` and is meant to be a complete, independent snapshot.

### `staging.coingecko_coin_history`
Raw landing zone for the **backfill** pipeline (`etl/backfill_market_history.py`), one row per coin per
explicit `snapshot_date`. `UNIQUE (coin_id, snapshot_date)` + `ON CONFLICT DO NOTHING` makes
re-running a backfill for an already-loaded date a safe no-op.

Migration `030` adds the same non-negative/positive-rank CHECK constraints to both staging tables,
so bad values are rejected at the very first landing point, not just at the warehouse fact tables.

## Incremental loading

The live pipeline's "already loaded" gate is `audit.etl_run.loaded_at`:
`etl_load_warehouse.select_batch` only picks a `coingecko_market_snapshot` batch that is
`status = 'succeeded' AND loaded_at IS NULL`; after a successful warehouse load, that batch's
`loaded_at` is stamped, permanently removing it from future candidates — a repeated `run_etl` call
with no new staging batch simply has nothing to do. The backfill pipeline uses a different but
equivalent mechanism: it pre-checks `fact_exists()` for each (coin, date) pair before even calling
the CoinGecko API, so a resumed/re-run backfill only fetches what's actually missing.

The full path: **source → staging → dimensions → facts → analytics views**:
1. `ingest_market_data.run_ingest` fetches CoinGecko and stages it, recording an `audit.etl_run`
   row for the ingestion itself.
2. `etl_load_warehouse.run_etl` picks an unloaded staging batch, ensures the `dim_date` row exists,
   and for every staged coin: `upsert_dim_coin` (SCD2) then `upsert_fact_market_snapshot`. All of
   this happens inside one transaction per batch — `conn.commit()` once at the end, `conn.rollback()`
   and an `audit.etl_run.status = 'failed'` record on any exception. A failed load cannot leave a
   partially-loaded, misleading batch: either every row in the batch lands, or none does.
3. `analytics.*` views read from `dw` (or, for `analytics.current_market_live` specifically, directly
   from `staging` — see below) with no separate load step; they're always current as of the last
   successful fact insert.

`database/bootstrap_db.py` applies schema migrations idempotently via a `public.schema_migrations` ledger
(added in this review — see `KNOWN_LIMITATIONS.md`/`31-production-readiness-and-polish.md` for the
bug this fixed): each `db/**/*.sql` file is applied at most once, tracked by filename, so re-running
bootstrap against an already-migrated database is a safe no-op rather than replaying old
`CREATE OR REPLACE VIEW` migrations that a later migration has since widened.

## Why `analytics.current_market_live` reads from staging, not `dw`

Every other `analytics.*` view is a straightforward projection of `dw` tables. `current_market_live`
is the one deliberate exception: it reads the **most recent ingestion run's staging rows** directly,
bypassing the fact table, so the "Take New Snapshot" button and the Dashboard's live refresh show
data immediately, without waiting for the (separate, sometimes-delayed) ETL step to promote it into
`dw.fact_market_snapshot`. This is why it also carries `price_change_percentage_24h` (CoinGecko's own
figure, staged but never loaded into `dw`) — a field the daily-grain fact table has no room for
since it's a rolling 24h figure, not a point-in-time observation.

## Example analytical questions this model supports

See `ANALYTICS_GUIDE.md` for a worked list; in short: point-in-time snapshots, historical trend
lines per coin, period-over-period movers/volatility over arbitrary date ranges, and rank movement
— all traceable back to a real, deduplicated warehouse row, never an estimate.
