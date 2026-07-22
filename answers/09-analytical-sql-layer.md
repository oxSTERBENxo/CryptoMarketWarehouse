# Milestone: Analytical SQL Layer

## Purpose of each view

- `analytics.latest_snapshot` — one row per coin as of the most recently loaded date in the fact table. Foundational "current state" view; the other per-coin views build on it instead of each re-deriving "what's the latest date."
- `analytics.current_market_overview` — single-row aggregate rollup of `latest_snapshot` (coin count, total market cap, total 24h volume) — the "at a glance" tile.
- `analytics.top_market_cap` — `latest_snapshot` ranked by market cap, with our own computed `market_cap_position` column, deliberately named apart from `market_cap_rank` (CoinGecko's own value, also present) to avoid confusion.
- `analytics.top_volume` — same idea, ranked by 24h volume.
- `analytics.market_history` — full historical series: every fact row joined to its date and to the coin attributes current when that row was loaded (via `coin_key`, so it's SCD2-correct) — what a trend chart would query.

## Why analytics is separate from dw

`dw` is the source of truth, shaped by ETL/loading concerns (surrogate keys, SCD2 bookkeeping, grain constraints). `analytics` is the consumption contract: readable columns, pre-joined dimensions, no ETL plumbing exposed. Future APIs/dashboards depend on this stable read surface instead of the warehouse's internal structure, and the "read-only from dw, never staging" rule is enforced structurally — nothing outside `analytics` needs staging visibility.

## Files created / modified

| File | Purpose |
|---|---|
| `db/schema/001_create_schemas.sql` | Added `CREATE SCHEMA IF NOT EXISTS analytics;` + comment (existing script, safe to rerun). |
| `db/analytics/008_latest_snapshot.sql` | `analytics.latest_snapshot` |
| `db/analytics/009_current_market_overview.sql` | `analytics.current_market_overview` |
| `db/analytics/010_top_market_cap.sql` | `analytics.top_market_cap` |
| `db/analytics/011_top_volume.sql` | `analytics.top_volume` |
| `db/analytics/012_market_history.sql` | `analytics.market_history` |
| `README.md` | Added the analytics schema/views section and updated the bootstrap description. |

All views use `CREATE OR REPLACE VIEW`, inherently idempotent — no `IF NOT EXISTS` needed.

## Bootstrap verification

Ran `bootstrap_db.py` — picked up and applied all 5 new files automatically, in correct dependency order (`008_latest_snapshot` before the views that build on it), alongside every prior script. Confirmed via `psql`: `analytics` schema exists, all 5 views listed in `information_schema.views`. Reran bootstrap a second time — all scripts reported `OK` again, exit code 0 (idempotent, matches the existing bootstrap guarantee).

Confirmed via `pg_views` that no view's definition references `staging`.

## Live query verification (against real warehouse data: 1 date, 20 coins, 20 facts)

**`current_market_overview`:**
```
 snapshot_date | coin_count | total_market_cap_usd | total_volume_24h_usd
 2026-07-22    |         20 |     2148287214811.00 |       99354358921.00
```

**`top_market_cap` (top 5):** Bitcoin, Ethereum, Tether, BNB, USDC — in that order, matching CoinGecko's own `market_cap_rank`.

**`top_volume` (top 5):** Tether, Bitcoin, USDC, Ethereum, Solana — correctly a *different* order from `top_market_cap` (stablecoins trade more volume relative to market cap), confirming independent ranking logic.

**`latest_snapshot` (5 rows):** Bitcoin/Ethereum/Tether/BNB/USDC with real prices and `market_cap_rank` 1–5.

**`market_history` (5 rows):** all from `2026-07-22` (only one date loaded so far), correctly ordered by date then coin — will show multiple dates once more batches are ETL'd on different days.

All 5 views return correct, real results from the live warehouse. No git commit was created.
