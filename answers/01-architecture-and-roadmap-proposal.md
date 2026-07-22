# Architecture & Roadmap Proposal

## Current state

Confirmed: this is an untouched PyCharm scaffold — `main.py` is the default "Hi, PyCharm" template, `.venv` exists (Python 3.14.0), no packages installed, no git commits yet. Docker CLI is available on this machine (useful for running Postgres locally).

## Architecture overview

The system is a pipeline with a data warehouse at its core, and everything else (API, frontend, AI agent, paper trading) reads from that warehouse rather than talking to raw sources directly:

```
CoinGecko API
     │
     ▼
[Ingestion]      raw JSON landed as-is (files or raw table), no transformation
     │
     ▼
[Staging]        typed, cleaned, deduplicated rows in Postgres — still "flat", not modeled
     │
     ▼
[ETL]            transforms staging → dimensional model (incremental + SCD2)
     │
     ▼
[Data Warehouse] Star Schema in Postgres — the single source of truth
     │
     ├──▶ [OLAP / analytical views]  — pure SQL, no app code
     │
     ▼
[FastAPI backend]  — reads DW, exposes REST/GraphQL endpoints
     │
     ▼
[React frontend]  — historical analysis, paper trading UI
     │
[AI agent]  — reads DW (and maybe live API) to produce market commentary
[Paper trading]  — its own transactional tables (portfolio, orders, fills), priced using DW facts
```

Two things worth calling out now, because they affect early decisions even though we won't build them yet:

- **Paper trading is transactional, not analytical.** It needs its own OLTP-style tables (accounts, orders, positions) separate from the star schema — the DW feeds it prices, it doesn't live inside the DW.
- **The AI agent is a consumer, not a layer everything flows through.** It queries the DW (and later maybe the API) — it doesn't sit in the pipeline.

## Tech stack (proposed, not installed yet)

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.14 (already in `.venv`) | Already set up |
| Warehouse | PostgreSQL, via Docker Compose | Portable, matches "professional DW" goal, Docker is available on this machine |
| DB access | SQLAlchemy Core (not full ORM) + raw SQL for DW queries | Star schemas are query-heavy; Core gives control without ORM ceremony |
| Schema migrations | Alembic | Warehouse schemas evolve (new dims, SCD2 columns) — want versioned, reviewable DDL from day one |
| Config | `pydantic-settings` + `.env` | Typed config, no scattered `os.environ` calls |
| Dependency management | `pyproject.toml` + `uv` (or plain `pip` if you'd rather not add a tool) | Your call — flagging as a decision point |
| Orchestration (later) | Plain script + cron/Task Scheduler at first; Airflow/Dagster only if/when complexity justifies it | Avoid infra weight before there's a real scheduling problem |
| API | FastAPI | Already in your list |
| Frontend | React | Already in your list |

## Data model direction (for later milestones, not now)

- **Staging**: one table per CoinGecko endpoint, close to the raw JSON shape, just typed and deduplicated. No business logic.
- **Warehouse (star schema)**:
  - `dim_date`, `dim_coin` (SCD2 — name/category/symbol can change), `dim_exchange` (added when exchange-level data enters)
  - `fact_market_snapshot` (grain: one row per coin per snapshot time — price, market cap, volume, rank)
  - Later facts (OHLCV candles, portfolio trades) get added as new features arrive, not speculatively now.
- **Incremental loading**: driven by a watermark (last-loaded timestamp) per source table, checked before each ETL run.

None of this gets built yet — it's here so the first milestone has a clear target to grow toward.

## Roadmap (milestones, each a deployable/demoable slice)

- **M0 — Project foundation** *(proposed first milestone, see below)*
- **M1 — Raw ingestion**: pull one CoinGecko endpoint (`/coins/markets`), land raw JSON, nothing modeled yet
- **M2 — Staging layer**: typed staging table in Postgres, idempotent load from raw
- **M3 — First star schema**: `dim_date`, `dim_coin`, `fact_market_snapshot`, full-refresh ETL from staging
- **M4 — Incremental loading**: watermark-based, no more full refreshes
- **M5 — SCD2 on `dim_coin`**
- **M6 — OLAP layer**: analytical SQL views (price trends, rankings over time)
- **M7 — FastAPI backend** over the warehouse
- **M8 — React frontend** (historical charts first)
- **M9 — Historical analysis features**
- **M10 — Paper trading** (own transactional schema + engine)
- **M11 — AI market analysis agent**

Each milestone should end with something runnable end-to-end, not a partial layer.

## Proposed first milestone: M0 — Project foundation

Deliberately boring — no ingestion, no warehouse tables yet. Just the scaffolding so M1 has somewhere to land:

1. Repo layout (`src/` package, `tests/`, no premature subfolders like `etl/` or `api/` until they hold something)
2. Dependency management file (`pyproject.toml`) — clean, no `main.py` template cruft
3. `docker-compose.yml` for local Postgres
4. Config loading (`pydantic-settings` reading `.env`) — proves the app can read a `DATABASE_URL`
5. Alembic wired up, empty migration baseline
6. One smoke test: connect to Postgres, confirm the connection works

Deliverable: `python -m src.something` (or a test) that proves "the app can reach Postgres" — nothing else. That's the whole milestone.

---

Open decisions before starting M0: **uv vs plain pip** for dependency management, and whether to use Docker Compose for Postgres or a locally-installed instance.
