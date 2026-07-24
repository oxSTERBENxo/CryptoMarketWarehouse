# Demo Guide

A short walkthrough for a university demonstration, covering every major feature and the
deterministic-vs-AI architecture that ties them together. Assumes the backend (`uvicorn`), frontend
(`npm run dev`), PostgreSQL, and (for the AI steps) a local Ollama instance are all running — see
`LOCAL_DEVELOPMENT.md` for exact startup commands.

## Suggested flow (10-15 minutes)

### 1. Warehouse Health (developer view — type `/warehouse-health` directly)

Start here — it's the most credible way to open a data-warehouse demo, since it proves the
warehouse is real and self-describing rather than asserting it verbally.

Note this is a **developer/operations page**: it's intentionally not in the user navigation, so
navigate to `http://localhost:5173/warehouse-health` by URL. Mention that end users never see it —
that's part of the polish story.

- Point out the six deterministic checks (Database, Data Quality, Duplicate Check, Missing-Date
  Coverage, Stale Coins, Scheduler), each Healthy/Warning/Error/Unknown with a plain-English reason.
- Point out the warehouse statistics: fact row counts (daily vs. hourly — two separate grains, see
  `DATA_WAREHOUSE_MODEL.md`), current vs. historical coin-dimension row counts (the SCD Type 2
  history), and the latest successful/failed pipeline runs.

### 2. Dashboard (`/`)

- The **AI Market Summary** card: press Generate, then point out that the headline figures
  (direction, gainers/losers counts, momentum) are computed in Python before the AI is ever called
  — the AI only writes the three bullet-point sections underneath. This is the deterministic/AI
  split every AI feature in the app follows (see `AI_FEATURES.md`).
- **Data Collection** status card: shows the latest warehouse snapshot and whether the scheduler
  is enabled — most demo environments run with it disabled and rely on manual snapshots/backfill.
- Press **Take New Snapshot** to show a live ingest → ETL cycle happening in real time, then point
  out the Top Market Cap / Top Volume / Latest Snapshot tables updating.

### 3. Analytics Explorer (`/analytics-explorer`)

- Pick a date preset (e.g. 90D), a metric (e.g. Price), and an analysis (e.g. "Increased by at
  least X%"), set a threshold, and press Run Analysis.
- Point out the summary cards (results found, average change, largest increase/decrease) and the
  sortable, paginated results table.
- Click a coin's row — this drills into Coin Details with the exact analyzed date range carried
  over via the URL (`?from=&to=`).
- Press the browser Back button to show the Explorer restores the exact query and results, rather
  than resetting to a blank form.
- Export the results as CSV.

### 4. Coin Details (from the Explorer drill-down, or `/coins/btc`)

- Show the historical/intraday charts and period summary for the carried-over range.
- Press Generate on the **AI Coin Analysis** card: point out the Coin Health badges (price trend,
  volatility, liquidity, market-cap tier) are all deterministic classifications, and the AI writes
  the five interpretive sections underneath them.

### 5. Portfolio → Paper Trading tab (`/portfolio`)

- Show the simulated account (starting cash balance, no real money involved) and execute a buy or
  sell against a live warehouse price.
- Switch to the **AI Portfolio Review** tab/card: point out the Portfolio Health badges
  (diversification score, concentration risk) are computed from the account's actual holdings
  before the AI writes its interpretation.

### 6. Market Leaders (`/market-leaders`)

- Switch between Today/7D/30D/90D/1Y to show the same gainers/losers/volatility computation over
  different windows, and that "Today" is powered by the separate intraday fact table (not an
  estimate from daily data).

### 7. Settings (`/settings`)

- Switch the appearance between Light, Dark, and System — every page, table, chart, and dialog
  follows instantly, and the choice survives a reload (localStorage).
- Switch the language to **Македонски** and click through a page or two: navigation, titles,
  buttons, table headers, and even number/date formatting all follow the selected locale. Switch
  back to English (or leave it — the choice also survives reloads).

### 8. Wrap-up: architecture and deterministic-vs-AI responsibilities

- **Warehouse**: CoinGecko → staging (append-only) → dimensions (SCD Type 2 `dim_coin`) → facts
  (`fact_market_snapshot` daily, `fact_market_intraday` sub-daily, both grain-enforced by real
  UNIQUE constraints) → analytics views. See `ARCHITECTURE.md`/`DATA_WAREHOUSE_MODEL.md`.
- **Analytics**: every percent-change/volatility figure across every feature uses the same formula
  and the same zero/missing-data guard — see `ANALYTICS_GUIDE.md`.
- **AI**: never computes a number; only interprets numbers already computed deterministically, and
  degrades to a fully-populated non-AI fallback if its response can't be parsed. See
  `AI_FEATURES.md`.

## If something isn't available

- **Ollama isn't running**: the AI cards show a clear "AI provider unavailable" error with a Retry
  button (not a silent blank card) — `/ai/health` reports this too. Every other feature is
  unaffected, since none of them depend on the AI layer.
- **No warehouse data yet**: Warehouse Health, Dashboard, and Market Leaders all show an
  explanatory empty state rather than an error; run `python -m database.bootstrap_db` then
  `python -m etl.ingest_market_data && python -m etl.load_warehouse` (or press Take New Snapshot once
  the frontend is up) to populate it.
