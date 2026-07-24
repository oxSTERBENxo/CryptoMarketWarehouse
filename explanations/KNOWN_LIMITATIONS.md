# Known Limitations

Deliberate scope boundaries and accepted trade-offs as of this review, not necessarily defects.
Where a limitation has a natural next step, it's cross-referenced in [Roadmap.md](Roadmap.md).

## Security & access

- **No authentication or authorization.** Every endpoint, including portfolio CRUD and the
  manual pipeline trigger, is open to anyone who can reach the API. This is explicitly
  single-user-by-design today (see `API.md`) — do not expose this API beyond a trusted network
  or localhost without adding auth first.
- **No rate limiting**, on either the public API or the outbound CoinGecko calls. A misbehaving
  or malicious client could trigger repeated `POST /admin/run-etl` calls (each rejected with
  `409` while one is in flight, so this can't run pipelines concurrently, but it can still spam
  CoinGecko once each finishes).
- **CORS must be explicitly configured for production.** `CORS_ALLOWED_ORIGINS` defaults to the
  Vite dev server only; a deployed frontend on a different origin will be silently blocked until
  the variable is set (see [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)).

## Data & concurrency

- **No connection pooling.** `database.get_connection()` opens a new PostgreSQL connection per
  request. Fine at the app's current traffic; would need a pool (e.g. `psycopg_pool`) or an
  external pooler (PgBouncer) before scaling up concurrent request volume.
- **Scheduler/pipeline state is in-process and in-memory.** The run-lock and
  `currently_running`/`last_success_at`/`last_failure_at` state in `services/pipeline_runner.py` don't
  coordinate across multiple `uvicorn` worker processes — running the scheduler with more than
  one worker will start one scheduled job per worker. See [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md).
- **No down-migrations.** `database/bootstrap_db.py` tracks which `db/**/*.sql` files have already been
  applied (`public.schema_migrations`), so re-running it is safe and only new files execute — but
  there's no way to roll a migration back, and a malformed filename (missing the `NNN_` numeric
  prefix) fails with an unhelpful `AttributeError` rather than a clear message. See
  `DATA_WAREHOUSE_MODEL.md`/`ETL_GUIDE.md`.
- **`dw.dim_coin`'s SCD2 has two narrow, unobserved gaps**, both accepted rather than fixed
  since neither is a demonstrated bug: no exclusion constraint prevents overlapping validity
  ranges among *historical* (non-current) rows for the same coin, and the read-then-write in
  `upsert_dim_coin` has no row lock, so two separate *processes* (not threads — in-process
  concurrency is already serialized) racing to update the same coin simultaneously could
  interleave. See `DATA_WAREHOUSE_MODEL.md`.
- **Coin symbol collisions aren't disambiguated.** Portfolio holdings are matched to warehouse
  prices by `upper(symbol)` (`analytics_repository.fetch_prices_for_symbols`), not by
  `coin_id`. If CoinGecko ever tracks two different coins sharing the same ticker symbol within
  the currently-tracked top-N, one would silently shadow the other when pricing a holding.

## Frontend

- **Single JS bundle, no code-splitting.** `npm run build` reports one bundle over the default
  500 KB warning threshold (~205 KB gzipped), driven mostly by `recharts` — acceptable today, but
  only the coin-details/intraday charts need charting.
- **The Portfolio page manages one manual-holdings portfolio at a time** in the UI even though the
  backend supports many (`GET /portfolios` returns a list) — a deliberate UI scope choice, not a
  backend limit.
- **No generic design-system components** (`Button`/`Badge`/`Tabs`/`Card`) — each page/component
  styles its own; deliberate, since the existing plain-CSS-per-component pattern is consistent
  enough in practice that introducing a shared component library wasn't justified by any actual
  inconsistency found in this review's design-consistency pass.
- **AI-generated text is not localized.** UI labels around the AI features are fully translated,
  but the bullet content the local LLM writes (Market Summary insights, Coin Analysis
  interpretation, Portfolio Review) arrives in whatever language the model produces — English
  today. Passing the selected language into the AI prompts is a possible follow-up; it was left
  out deliberately to avoid touching the AI endpoints.
- **The Warehouse Health page stays English-only.** It's a developer/operations tool, removed
  from the user navigation and reachable only by direct URL (`/warehouse-health`), so it was
  deliberately excluded from the English/Macedonian localization pass. The backend `/health/*`
  endpoints are unaffected.
- **Backend error messages are not localized.** `ApiError` messages surfaced in error states come
  from the API in English; the surrounding UI (retry buttons, error-state chrome) is translated.
- **Only two locales ship today** (English, Macedonian). The structure supports more — see
  README "Theming and localization" for the add-a-language steps — and a test enforces key parity
  between locale files so a partial translation can't ship silently.

## Operations

- **No CI pipeline** (no `.github/workflows`, no equivalent) — tests, lint, and build are run
  manually today.
- **No containerization for the backend or frontend** — only PostgreSQL has a
  `docker-compose.yml` service. See [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) for how to run the other two
  without one.
- **No point-in-time recovery / WAL archiving** documented or configured — backup strategy is
  periodic `pg_dump` only. See [BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md).
- **No structured/centralized logging.** `logging_config.get_logger` gives each module its own
  stream handler at INFO level; there's no request-ID correlation, log aggregation, or
  structured (JSON) log output beyond uvicorn's own access log.
