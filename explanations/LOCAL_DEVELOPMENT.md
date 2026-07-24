# Development

This is the day-to-day contributor guide. For the production-facing setup see
[PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md); for system design see [ARCHITECTURE.md](ARCHITECTURE.md).

## Prerequisites

- Python 3.14 (a `.venv/` is already present in the repo; recreate it with
  `python -m venv .venv` if needed)
- Node.js 20+
- Docker (for local PostgreSQL via `docker-compose.yml`) — or any PostgreSQL 16 instance you
  point `.env` at

## First-time setup

```bash
# Database
docker-compose up -d
cp .env.example .env                    # adjust POSTGRES_PASSWORD etc. if needed

# Backend
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/pip install -r requirements-dev.txt   # adds pytest, httpx
.venv/Scripts/python -m database.bootstrap_db     # applies db/ migrations, in numeric order

# Frontend
cd frontend
cp .env.example .env
npm install
cd ..
```

## Running everything locally

```bash
# Terminal 1 — backend
.venv/Scripts/python -m uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Backend: http://localhost:8000 (docs at `/docs`). Frontend: http://localhost:5173. The dashboard
has nothing to show until the warehouse has at least one snapshot — run the ingest/ETL scripts
once (see below), or set `ENABLE_SCHEDULER=true` and wait for the first scheduled run, or call
`POST /admin/run-etl`.

## Loading data manually

```bash
.venv/Scripts/python -m etl.ingest_market_data --limit 100   # CoinGecko -> staging
.venv/Scripts/python -m etl.load_warehouse                    # staging -> warehouse
```

Both are safe to rerun: ingestion always appends a new staging batch; the ETL only ever loads
each staging batch once (`audit.etl_run.loaded_at`), and a rerun of `database/bootstrap_db.py` only applies
migrations it hasn't already applied (tracked in `public.schema_migrations`) — a no-op against an
already-migrated database.

## Tests

```bash
.venv/Scripts/python -m pytest              # backend, no live DB required
cd frontend && npm test                     # frontend — vitest run
cd frontend && npm run lint                 # oxlint
cd frontend && npm run build                # tsc -b && vite build (typechecks + bundles)
```

The backend suite stubs the database layer with `monkeypatch`/fake cursors (see `tests/test_*.py`)
rather than hitting a live PostgreSQL connection, so it runs the same in CI as it does locally, and
never depends on the developer's local `.env`. `ENABLE_SCHEDULER` is unset/`false` by default, so
the suite never starts a background job.

The frontend suite (Vitest + React Testing Library, `frontend/src/**/*.test.tsx`) covers page- and
component-level behavior: loading/error/empty states, the Analytics Explorer query lifecycle, AI
card refresh-failure preservation, the Warehouse Health page's status rendering (a
developer-only page, reachable by direct URL), theme (Light/Dark/System) resolution and
persistence, and English/Macedonian localization (language detection, persistence, `<html lang>`,
locale-aware formatting, and en/mk key parity). See
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) and [Roadmap.md](Roadmap.md) for current gaps.

## Conventions

- **Layering**: `routes` (HTTP concerns: status codes, request/response models) →
  `service` (business rules, only where there is real logic — e.g. portfolio valuation) →
  `repository` (parameterized SQL, no business logic). Analytics skips the service layer because
  there's no business logic beyond a query; portfolio has one because valuation is real logic.
  Keep new features in this shape rather than mixing SQL into routes.
- **Migrations**: every file under `db/` is numbered (`NNN_description.sql`) and
  auto-discovered by `database/bootstrap_db.py` in numeric order across all subfolders — the subfolder
  (`schema`, `dw`, `staging`, `audit`, `analytics`, `app`) is just for organization, not
  ordering. `database/bootstrap_db.py` tracks which files have already run in `public.schema_migrations`
  and only applies new ones, so a migration only needs to be idempotent against a **fresh**
  database, not against being replayed on an already-migrated one — but a `CREATE OR REPLACE VIEW`
  that narrows or reorders an existing view's columns will still fail if that view is ever
  bootstrapped from scratch out of order, so keep new columns appended at the end (see the
  comments in `db/analytics/027_views_add_image_url.sql` for why).
- **Error translation**: repository functions raise driver-level exceptions as-is; service
  functions translate the ones that matter into named exceptions
  (`PortfolioNotFoundError`, `DuplicateHoldingError`, ...); routes translate those into HTTP
  status codes. Don't catch broad `Exception` in a route/dependency around request-handling code
  — see the `_get_db()` docstrings in `analytics/routes.py`/`portfolio/routes.py` for why that
  specifically breaks FastAPI's validation-error reporting.
- **Frontend data fetching**: use `useApiData` for anything hitting the backend; don't call
  `fetch`/`apiGet` directly from a component. Add new endpoints to `api/analytics.ts` /
  `api/portfolio.ts` / `api/health.ts` as thin typed wrappers, mirroring the existing ones.
