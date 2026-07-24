# Scheduler

The warehouse can grow automatically: a background job periodically runs the same ingest → ETL
pipeline as the CLI scripts, in-process, using [APScheduler](https://apscheduler.readthedocs.io/).
This is a single-node app with a blocking (`requests` + `psycopg`) pipeline, so an in-process,
thread-based scheduler is the appropriate fit — no broker, queue, or extra service required. See
[ARCHITECTURE.md](ARCHITECTURE.md) for how this fits into the rest of the system, and
[PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) for the multi-worker caveat before enabling this in production.

## Configuration

Environment variables (see `.env.example`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `ENABLE_SCHEDULER` | `false` | Starts the background job on API startup when `true`. Disabled by default so `uvicorn`/tests never run it unasked. |
| `SCHEDULER_INTERVAL_MINUTES` | `60` | Minutes between scheduled runs. |
| `SCHEDULER_CURRENCY` | `usd` | Quote currency for scheduled/manual pipeline runs. |
| `SCHEDULER_LIMIT` | `100` | Number of coins fetched per run. |
| `SCHEDULER_ORDER` | `market_cap_desc` | CoinGecko ordering per run. |

## Behavior

- **Startup/shutdown**: starts once during FastAPI startup (`lifespan`) and shuts down cleanly on
  API shutdown. Starting it twice (e.g. re-entrant startup) is a no-op — it never creates a
  duplicate job (`replace_existing=True`, plus an explicit `_scheduler is not None and
  _scheduler.running` guard).
- **What each run does**: CoinGecko fetch → stage raw snapshot → run ETL → record `audit.etl_run`
  rows → log success/failure — the exact same `run_ingest`/`run_etl` functions used by the CLI
  scripts (`etl/ingest_market_data.py`, `etl/load_warehouse.py`), just orchestrated by
  `services/pipeline_runner.py` instead of `argparse`.
- **Concurrency**: scheduled and manual (`POST /admin/run-etl`) runs share one process-local
  lock (`threading.Lock`, non-blocking acquire). If a run is already in progress, a new one is
  skipped (scheduled trigger) or rejected with `409` (manual trigger) rather than running
  concurrently or queuing. APScheduler's own `coalesce=True, max_instances=1` back this up at the
  job level.
- **Manual trigger**: `POST /admin/run-etl` runs one pipeline cycle immediately and returns a
  JSON summary (ingest + ETL results, timing, or the error). This is independent of the scheduled
  job — it doesn't pause or reschedule it, it just competes for the same run-lock.
- **Health check**: `GET /health/scheduler` reports whether the scheduler is enabled/running,
  whether a run is currently in progress, the last successful/failed run timestamps, and the next
  scheduled run time.

## Operational notes

- The run-lock and state (`currently_running`, `last_success_at`, `last_failure_at`,
  `last_error_message`) are **in-memory and per-process**. They do not coordinate across multiple
  API worker processes — see the multi-worker caveat in [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md).
- A failed run does not retry automatically; it waits for the next scheduled tick (or a manual
  `POST /admin/run-etl`). `last_error_message` on `/health/scheduler` is the way to notice a
  failing pipeline without tailing logs.
- Every run — scheduled or manual, successful or failed — leaves an audit trail in
  `audit.etl_run` (two rows: one for the ingest, one for the ETL), independent of the in-memory
  state, so history survives process restarts even though the live status doesn't.
