# Deployment

This project ships a `docker-compose.yml` for **PostgreSQL only**; the FastAPI backend and the
React frontend are not containerized. This is deliberate for the project's current single-node
scale (see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)) — this document describes how to run all
three pieces on a server without a redesign of that setup.

## 1. Database

```bash
docker-compose up -d
```

Set `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_PORT` in `.env` before
starting it for the first time — `docker-compose.yml` reads them from the environment. Use a real
generated password in any non-local environment; `.env.example`'s `change_me` is a local-only
placeholder.

Then apply migrations once:

```bash
.venv/Scripts/python -m database.bootstrap_db
```

`database/bootstrap_db.py` is safe to rerun (every script is idempotent) — rerun it after pulling new
`db/` migrations.

## 2. Backend

```bash
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers <N>
```

Required environment variables (see `.env.example` for the full list with defaults):

| Variable | Required | Notes |
| --- | --- | --- |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Yes | No defaults — `database/connection.py` reads these via `os.environ[...]` and raises `KeyError` at first connection attempt if any are missing. |
| `CORS_ALLOWED_ORIGINS` | No | Comma-separated list of origins allowed to call the API. **Set this to your deployed frontend's origin(s)** — it defaults to the Vite dev server only, which will silently block a production frontend if left unset. |
| `ENABLE_SCHEDULER`, `SCHEDULER_INTERVAL_MINUTES`, `SCHEDULER_CURRENCY`, `SCHEDULER_LIMIT`, `SCHEDULER_ORDER` | No | See [Scheduler.md](Scheduler.md). |

**`--workers` and the scheduler don't mix.** Each uvicorn worker process runs its own `lifespan`
and therefore its own `BackgroundScheduler` — with `ENABLE_SCHEDULER=true` and more than one
worker, every worker starts its own scheduled job, so the pipeline would run once per worker per
interval instead of once. Either run a single worker process when the scheduler is enabled, or
run the scheduler as a separate single-instance process (e.g. a small script that just calls
`pipeline_runner.run_pipeline` on a cron/systemd timer) and leave `ENABLE_SCHEDULER=false` on
every API worker. The in-process design documented in the README assumes a single process; see
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

There is no connection pool — every request opens its own PostgreSQL connection
(`database.get_connection()`). This is fine at the app's current scale; under sustained load,
front it with PgBouncer or introduce a pool (e.g. `psycopg_pool`) before scaling up traffic or
worker count. See [Roadmap.md](Roadmap.md).

Put a reverse proxy (nginx, Caddy, a cloud load balancer) in front of uvicorn for TLS
termination; uvicorn itself is not meant to be exposed directly to the internet.

## 3. Frontend

```bash
cd frontend
cp .env.example .env    # set VITE_API_BASE_URL to the backend's public URL
npm install
npm run build            # emits static assets to frontend/dist/
```

`frontend/dist/` is a static site — serve it with any static file server or CDN (nginx, S3 +
CloudFront, Vercel/Netlify, etc.). `VITE_API_BASE_URL` is baked in at build time, so rebuild the
frontend if the backend's public URL changes.

Remember to add the frontend's deployed origin to the backend's `CORS_ALLOWED_ORIGINS`.

## Health checks

Point your process manager / load balancer's health check at `GET /health` (liveness) or
`GET /health/database` (readiness — verifies the DB is reachable). `GET /health/scheduler`
reports scheduler/pipeline status and is safe to poll but isn't itself a liveness signal.

## What this project does not provide

- A backend/frontend Dockerfile or a combined `docker-compose.yml` (only PostgreSQL is
  containerized today — see [Roadmap.md](Roadmap.md)).
- A CI/CD pipeline definition.
- TLS termination, authentication, or rate limiting — the API has none of these; see
  [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) before exposing it beyond a trusted network.
