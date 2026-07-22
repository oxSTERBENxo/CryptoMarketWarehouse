# Milestone: Initial Data Warehouse Structure

## Design rationale

**Grain of `fact_market_snapshot`: one row per coin per day.** Matches CoinGecko's point-in-time market data and the project's historical-analysis/portfolio-tracking goals — coarse enough to keep row counts sane before any ingestion exists, fine enough for trend analysis. Enforced with `UNIQUE(date_key, coin_key)`, not just documentation.

**`dw.dim_date`** — standard date dimension, one row per calendar day, needed for any time-based rollup. Uses a smart integer surrogate key (`YYYYMMDD`) — the conventional exception to "surrogate keys are meaningless," since it's the standard, sortable, human-readable pattern for date dimensions.

**`dw.dim_coin`** — SCD Type 2: one row per *version* of a coin's identifying attributes (`coin_id`, `symbol`, `name`), tracked via `valid_from`/`valid_to`/`is_current`. Names/symbols occasionally change, and historical facts must reflect what a coin was called at the time. A surrogate `coin_key` (identity column) is what the fact table references, never the natural `coin_id` — so each fact row points to the exact attribute-version current when the snapshot was taken. A partial unique index (`WHERE is_current`) enforces "at most one current row per coin."

**`dw.fact_market_snapshot`** — references both dimensions by surrogate key, carries the numeric measures CoinGecko's markets endpoint provides (`price_usd`, `market_cap_usd`, `volume_24h_usd`, `circulating_supply`, `market_cap_rank`), plus `dw_loaded_at` for lineage.

**`audit.etl_run`** — generic pipeline run log (name, start/end, status, rows processed, error message) — structure only, no ETL exists yet to populate it.

**Schemas:** `staging` (created empty — no tables until ingestion exists), `dw` (dimensional model), `audit` (operational metadata), kept separate so raw/modeled/operational data are never conflated.

## Files created

| File | Purpose |
|---|---|
| `db/schema/001_create_schemas.sql` | Creates `staging`, `dw`, `audit` schemas with descriptive comments. |
| `db/dw/002_dim_date.sql` | `dw.dim_date` — date dimension. |
| `db/dw/003_dim_coin.sql` | `dw.dim_coin` — SCD2 coin dimension, with the partial unique index enforcing one current row per coin. |
| `db/dw/004_fact_market_snapshot.sql` | `dw.fact_market_snapshot` — daily grain fact table, FKs to both dimensions, grain-enforcing unique constraint. |
| `db/audit/005_etl_run.sql` | `audit.etl_run` — pipeline run log. |

Numeric prefixes make execution order explicit (schemas → dimensions → fact, since the fact table's foreign keys depend on the dimension tables already existing).

## Verification

Ran all five scripts in order against the running `cryptomarketwarehouse-postgres` container — each executed without error. Confirmed via `psql`:
- Schemas `staging`, `dw`, `audit` all exist; `staging` correctly has zero tables.
- `dw` has exactly `dim_coin`, `dim_date`, `fact_market_snapshot`; `audit` has exactly `etl_run`.
- Constraint inspection (`pg_constraint`) confirms the fact table's two foreign keys (`date_key` → `dim_date`, `coin_key` → `dim_coin`), the grain-enforcing unique constraint, and the check constraints on `dim_coin` and `etl_run`.
- Row counts on all four tables are 0 — nothing populated, as required.

**All SQL scripts execute successfully on PostgreSQL — confirmed.**

## Commands to reproduce

```
Get-Content db\schema\001_create_schemas.sql | docker compose exec -T postgres psql -U crypto -d crypto_market_warehouse
Get-Content db\dw\002_dim_date.sql | docker compose exec -T postgres psql -U crypto -d crypto_market_warehouse
Get-Content db\dw\003_dim_coin.sql | docker compose exec -T postgres psql -U crypto -d crypto_market_warehouse
Get-Content db\dw\004_fact_market_snapshot.sql | docker compose exec -T postgres psql -U crypto -d crypto_market_warehouse
Get-Content db\audit\005_etl_run.sql | docker compose exec -T postgres psql -U crypto -d crypto_market_warehouse
```
