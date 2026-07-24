# Analytics Guide

How the analytical figures shown across the Dashboard, Coin Details, Market Leaders, Analytics
Explorer, and the AI features are computed, and the shared conventions that keep them consistent
with each other.

## Shared formulas

Every "percent change" in the app is the same formula: **`(end - start) / start * 100`**. Every
"volatility" figure is the same formula applied to the period's high/low instead of start/end:
**`(high - low) / low * 100`**. Both are guarded the same way everywhere: **the result is `NULL`
(SQL) / `None` (Python) whenever the denominator (`start` / `low`) is exactly zero or either
operand is missing** — never estimated, never reported as `0%`, never a division error.

| Layer | Where | What it computes |
|---|---|---|
| SQL | `analytics_repository._MOVER_FIELDS` (shared by `fetch_daily_movers` and `fetch_intraday_movers`) | `percent_change`, `volatility_percent` for the Dashboard/Market Leaders movers lists |
| SQL | `analytics_repository.fetch_history_summary` | `percent_change` for a single coin's Coin Details period summary |
| SQL | `analytics_explorer_repository.fetch_period_stats` | `percent_change`, `volatility_percent`, `dollar_change`, `rank_change` behind every Analytics Explorer analysis |
| Python | `metrics.safe_percent` / `metrics.percent_change` (`utils/metrics.py`) | Every Python-side percent figure: AI Coin Analysis volatility/distance-from-high-low/average daily movement, Manual Holdings and Paper Trading profit %, portfolio allocation % |

`tests/test_analytics_consistency.py` pins this down as an automated regression check: it asserts
the `_MOVER_FIELDS` and `fetch_period_stats` SQL expressions are byte-for-byte identical, and that
`metrics.safe_percent` produces the same result as the SQL `CASE WHEN low = 0 THEN NULL ELSE ...`
guard for the same inputs. If a future edit makes one formula diverge from the others, that test
fails.

### Why a shared Python helper but not a shared SQL function

The two SQL query builders (`analytics/repository.py`, `analytics/explorer_repository.py`) already
used textually identical `CASE WHEN ... END` expressions before this review — there was no
inconsistency to fix there, so they were left as they were rather than factored into a Postgres
function, which would add a layer of indirection for no behavior change. The Python call sites
(`ai/coin_analysis_service.py`, `portfolio/service.py`, `paper_trading/service.py`) had the same
formula but *different* zero/`None` guard spellings (`== 0`, truthiness, `> 0`) scattered across
five call sites — real, if currently harmless, duplication. `utils/metrics.py`'s `safe_percent`/
`percent_change` consolidate that into one guard, reused by all three modules.

## Edge cases, explicitly

- **Zero price**: a coin priced at exactly `0` as the period's `start`/`low` value makes
  percent-change/volatility undefined against it — every layer returns `NULL`/`None`, never `0%`.
  (As of this review, `dw`/`staging` CHECK constraints also reject negative prices outright — see
  `DATA_WAREHOUSE_MODEL.md`.)
- **Missing dates / fewer than 2 observations**: `fetch_daily_movers`, `fetch_intraday_movers`, and
  `fetch_period_stats` all exclude a coin from the result entirely (`HAVING observation_count >=
  2` / equivalent) rather than estimating a change from a single point.
- **Null rank**: `rank_change` is `NULL` whenever either endpoint's `market_cap_rank` is `NULL`
  (CoinGecko omits it for very new or very low-ranked coins), never treated as `0` movement.
- **First/last observation selection**: "first" and "last" always mean the earliest/latest
  `snapshot_date` (daily) or `observation_timestamp` (intraday) *actually present* in the
  requested range, from a real ingested row — never the requested range boundary itself if no
  observation lands exactly on it.
- **Date inclusivity**: date-range filters are inclusive on both ends (`snapshot_date >= from_date
  AND snapshot_date <= to_date`) everywhere a range is accepted.
- **Formatting/rounding**: figures are stored and returned as full-precision `NUMERIC`/`float`;
  rounding for display is a frontend concern (`frontend/src/utils/format.ts`), not baked into the
  warehouse or API layer, so a consumer that wants more precision than the UI displays already has
  it.

## Example analytical questions this model supports

- "Which coins moved the most (up or down) over the last 7/30/90/365 days?" — Market Leaders /
  Analytics Explorer "increased/decreased by %".
- "Which coin was most volatile this month?" — Analytics Explorer "volatility" analysis, or the
  Market Leaders volatility column.
- "How has Bitcoin's rank changed over the last year?" — Analytics Explorer "rank change"
  analysis, or Coin Details' period summary.
- "What's the average trading volume for a coin over a custom date range?" — Analytics Explorer
  "average volume" analysis.
- "Is this coin more volatile than usual right now, and is it in a bull or bear trend?" — AI Coin
  Analysis, built from the same `fetch_history_summary` figures as Coin Details.
