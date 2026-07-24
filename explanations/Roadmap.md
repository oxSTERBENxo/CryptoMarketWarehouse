# Roadmap

Ideas for future work, grouped by horizon. None of this is committed or scheduled — it's a
prioritized backlog derived from the gaps in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) and this
review's findings, for whoever picks up the project next.

## Near-term (low effort, clear value)

- **CI pipeline**: run `pytest`, `oxlint`, and `npm run build` on every push/PR (GitHub Actions
  or equivalent). The commands already exist and pass locally — this is wiring, not new work.
- **`CORS_ALLOWED_ORIGINS` in every deployment checklist**: now configurable (this review), but
  easy to forget — a startup-time warning log when it's left at the dev-only default in a
  non-debug run would catch this before it becomes a support ticket.
- **Frontend code-splitting**: lazy-load the coin-details route (and `recharts` with it) via
  `React.lazy`/dynamic `import()` so the dashboard and portfolio pages don't pay for charting
  they don't use.
- **Friendlier `database/bootstrap_db.py` error message** for a malformed migration filename, instead of
  an `AttributeError` traceback.

## Medium-term

- **Connection pooling** (`psycopg_pool` or PgBouncer) once concurrent request volume justifies
  it — see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).
- **A distributed run-lock** (e.g. a `SELECT ... FOR UPDATE` advisory lock in Postgres, or Redis)
  if/when the backend needs to run with more than one worker process while the scheduler stays
  enabled.
- **More frontend test coverage**: Vitest + React Testing Library is now in place (this review),
  covering the pages/components most likely to regress silently; `useApiData`'s retry/cancellation
  logic and `MetricChart`'s empty-data branch remain untested.
- **Backend/frontend Dockerfiles** and a combined `docker-compose.yml` (backend + frontend +
  postgres) for one-command local/staging spin-up.
- **Additional hosted-AI providers**: `AI_PROVIDER` now supports swapping between local Ollama and
  Groq (see `AI_FEATURES.md`). Future providers can follow the same `AIProvider` interface.

## Longer-term

- **Authentication** (even a single shared API key/token to start) before this API is exposed
  outside a trusted network, followed by real multi-user support if the single-portfolio design
  needs to become multi-account.
- **Multi-portfolio UI**: the backend already supports many portfolios per the REST API; the
  frontend intentionally shows one at a time today (see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)).
  A portfolio switcher/list view would unlock this without backend changes.
- **Additional data sources beyond CoinGecko**, if warehouse coverage needs to extend past its
  top-N market-cap/volume window (e.g. a specific coin that falls outside the tracked set).
- **Alerting on pipeline failures** (e.g. a webhook/email when `audit.etl_run.status = 'failed'`
  or `/health/scheduler.last_failure_at` moves), rather than relying on someone checking the
  health endpoint or logs.
- **Point-in-time recovery** for the database, if data durability requirements grow beyond what
  periodic `pg_dump` backups provide — see [BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md).
