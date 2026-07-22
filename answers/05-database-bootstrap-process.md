# Milestone: Repeatable Database Bootstrap Process

## Minimal changes identified

`database.py`'s `get_connection()` was reusable as-is. Idempotency gaps: `001_create_schemas.sql` was already safe to rerun (`CREATE SCHEMA IF NOT EXISTS`), but `002`-`005` used plain `CREATE TABLE`/`CREATE INDEX`/`CREATE UNIQUE INDEX`, which error on a second run. `COMMENT ON` statements were already idempotent.

## Files created / modified

| File | Change |
|---|---|
| `db/dw/002_dim_date.sql` | `CREATE TABLE` → `CREATE TABLE IF NOT EXISTS` |
| `db/dw/003_dim_coin.sql` | `CREATE TABLE` and `CREATE UNIQUE INDEX` → `IF NOT EXISTS` variants |
| `db/dw/004_fact_market_snapshot.sql` | `CREATE TABLE` and both `CREATE INDEX` statements → `IF NOT EXISTS` variants |
| `db/audit/005_etl_run.sql` | `CREATE TABLE` → `CREATE TABLE IF NOT EXISTS` |
| `bootstrap_db.py` | New. Discovers `db/**/*.sql`, sorts by numeric filename prefix, runs each file as its own transaction over one connection from `database.get_connection()`. |
| `README.md` | Replaced the manual per-file instructions with the single bootstrap command. |

## How ordering and failure handling work

`discover_scripts()` recursively globs `db/**/*.sql` and sorts by the leading digits of each *filename* (via regex), not by full path — so folder names (`schema/`, `dw/`, `audit/`) don't affect ordering; only the `001`-`005` prefixes do. This keeps ordering correct regardless of how the SQL is organized into subfolders.

One connection is opened via the existing `get_connection()`. For each script, in order: execute its full contents (psycopg3 allows multiple `;`-separated statements in one `execute()` when no parameters are bound), then `commit()`. On any exception, `rollback()`, print the file that failed and the error, print a failure message, and return `1` immediately — no later scripts run after a failure, since they may depend on earlier ones. On success of every script, print a final success message and return `0`. `sys.exit(main())` turns that into the process exit code.

## Verification

**Fresh empty database:** ran `docker compose down -v` (safe — the volume held only empty structural tables from the previous milestone) then `docker compose up -d`, waited for the health check to pass, then ran `bootstrap_db.py`. All 5 scripts printed `OK` in order (`001` → `002` → `003` → `004` → `005`), final message "Bootstrap completed successfully.", exit code `0`. Confirmed via `psql`: `staging`/`dw`/`audit` schemas exist, `dw` has exactly `dim_coin`/`dim_date`/`fact_market_snapshot`, `audit` has exactly `etl_run`.

**Rerun on already-initialized database:** ran `bootstrap_db.py` again immediately, no changes to the database in between. All 5 scripts again printed `OK`, exit code `0`. Verified no duplicates: table counts unchanged (`dw`=3, `audit`=1), exactly 8 indexes in `dw` (one set, not two), and all four tables still have 0 rows.

**Result: bootstrap is safe to rerun — no duplicate objects, no errors, non-zero exit only on real failure.**

## Bootstrap command

```
.venv\Scripts\python bootstrap_db.py
```
