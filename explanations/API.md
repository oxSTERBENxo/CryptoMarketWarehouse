# API Reference

The backend is a FastAPI app. Interactive, always-up-to-date docs are served at **`/docs`**
(Swagger UI) and **`/redoc`** whenever the API is running — this file is a quick static
reference; the running `/docs` endpoint is authoritative for exact schemas.

Base URL in local development: `http://localhost:8000` (or whatever `VITE_API_BASE_URL` points
the frontend at — see [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md)).

## Health

| Method | Path | Returns | Notes |
| --- | --- | --- | --- |
| `GET` | `/health` | `{"status": "healthy"}` | Liveness only — no dependencies checked. |
| `GET` | `/health/database` | `{"status": "healthy"}` | Runs `SELECT 1`. `503` if the database is unreachable. |
| `GET` | `/health/scheduler` | See below | Scheduler + pipeline status. |
| `GET` | `/health/warehouse` | See `warehouse_health_models.WarehouseHealthResponse` | Aggregated Warehouse Health page data (DB status, ETL run history, fact/dimension counts, duplicate-key check, missing-date coverage, stale coins, environment). Always `200` — a degraded warehouse is carried in the payload's own `overall_status`/per-check fields, never an HTTP error. |

`GET /health/scheduler` response shape:

```json
{
  "enabled": false,
  "running": false,
  "interval_minutes": 60,
  "currently_running": false,
  "last_success_at": "2026-07-23T11:32:52.965418Z",
  "last_failure_at": null,
  "next_run_time": null
}
```

## Analytics

All analytics endpoints are read-only and backed by `analytics.*` SQL views (see
[ARCHITECTURE.md](ARCHITECTURE.md)). `limit`/`order` are validated query parameters — a value
outside their allowed range (e.g. `limit=99999`, `order=sideways`) returns `422`, not `503`.

| Method | Path | Query params | Notes |
| --- | --- | --- | --- |
| `GET` | `/analytics/overview` | — | `404` if no snapshot has been loaded yet. |
| `GET` | `/analytics/latest` | `limit` (1–500, optional), `order` (`asc`\|`desc`, default `desc`) | One row per coin, latest snapshot. |
| `GET` | `/analytics/top-market-cap` | `limit` (1–500, default 10), `order` | `market_cap_position` is a global rank, unaffected by `limit`/`order`. |
| `GET` | `/analytics/top-volume` | `limit` (1–500, default 10), `order` | `volume_position` is a global rank, unaffected by `limit`/`order`. |
| `GET` | `/analytics/history/{coin_symbol}` | `limit` (1–1000, optional), `order` (default `asc`), `from_date`, `to_date` (`YYYY-MM-DD`) | Case-insensitive symbol match. `404` if the symbol has never appeared in any snapshot. `400` if `from_date > to_date`. Empty list if the symbol is valid but no rows fall in range. |
| `GET` | `/analytics/history/{coin_symbol}/summary` | `from_date`, `to_date` (optional) | Period start/end price, percent change, min/max/avg price. `404` if no rows in range. |
| `GET` | `/analytics/current-market` | `limit`, `order` | Live values from the most recent ingestion run, independent of the daily fact-table grain. |
| `GET` | `/analytics/intraday/{coin_symbol}` | `from_date`, `to_date`, `order`, `limit` | Sub-daily observations from `dw.fact_market_intraday`. |
| `GET` | `/analytics/intraday/{coin_symbol}/today` | — | Convenience wrapper for "today's" intraday observations. |
| `GET` | `/analytics/market-leaders` | `period` (`today`\|`7d`\|`30d`\|`90d`\|`1y`), `limit` | Gainers/losers/highlights for the period. `422` on an invalid `period`. |

### Analytics Explorer

Purely deterministic (no AI, no external API) interactive historical queries over
`analytics.market_history`. See `ANALYTICS_GUIDE.md` for the shared formulas behind every figure.

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| `POST` | `/analytics/explorer/query` | `ExplorerRequest` (metric, condition, date range, optional threshold/filters/sort/pagination) | Returns matching rows plus a summary over every qualifying row (not just the current page). |
| `POST` | `/analytics/explorer/export` | Same as above | Returns `text/csv`, capped at 1000 rows. String cells starting with `= + - @` are escaped against spreadsheet formula injection. |

## AI

Every AI response separates deterministic figures (computed before the AI is ever called) from the
AI-authored interpretation — see `AI_FEATURES.md`. Failures map to `503` (provider unreachable),
`504` (timeout), or `502` (other provider error); a malformed-but-received AI response degrades to
a fully-populated non-AI fallback instead of failing the request.

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/ai/health` | Checks the configured provider answers a trivial prompt. |
| `GET` | `/ai/providers` | Lists known providers and which is active. |
| `POST` | `/ai/market-summary` | Dashboard-wide AI Market Summary. |
| `POST` | `/ai/coin-analysis/{coin_symbol}` | AI Coin Analysis. `404` if the symbol has no current warehouse snapshot. |
| `POST` | `/ai/portfolio-review` | AI Portfolio Review, over the paper-trading account. |

## Paper Trading

Simulated buy/sell against live warehouse prices, starting from a configurable cash balance
(`PAPER_TRADING_INITIAL_CASH`) — no real money involved.

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| `GET` | `/paper-account` | — | Created lazily on first use. |
| `POST` | `/paper-account/reset` | — | Resets cash balance and clears transaction history. |
| `GET` | `/paper-portfolio` | — | Valuation derived by replaying transaction history — never stored. |
| `POST` | `/paper-trades/buy` | `{coin_symbol, quantity}` | `400` on insufficient cash or unknown symbol. |
| `POST` | `/paper-trades/sell` | `{coin_symbol, quantity}` | `400` on insufficient holdings. |
| `GET` | `/paper-trades` | `limit` | Transaction history, most recent first. |

## Admin

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/admin/run-etl` | Runs one ingest → ETL cycle immediately, using the same code path as the scheduler. `409` if a run (scheduled or manual) is already in progress. Returns a JSON summary (status, timing, rows ingested/loaded, or the error message). |
| `POST` | `/admin/refresh-market-data` | The Dashboard's "Take New Snapshot" button: ingest → ETL, plus one `dw.fact_market_intraday` row per coin sharing a single timestamp, then prunes old intraday rows. `409` if a run is already in progress. |
| `GET` | `/admin/data-recovery-status` | Startup gap-detection/backfill job's current state (used by the Dashboard's recovery banner). |

## Portfolio

No authentication — single-user by design (see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)).
Valuation fields are computed at read time from the warehouse, never persisted; see the
README's "Portfolio management" section for the exact formulas.

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| `GET` | `/portfolios` | — | All portfolios, each with holdings + valuation. |
| `POST` | `/portfolios` | `{name, description?}` | `201`. `name` must be non-blank (`422` otherwise). |
| `GET` | `/portfolios/{id}` | — | `404` if missing. |
| `PUT` | `/portfolios/{id}` | `{name, description?}` | Replaces name/description. `404` if missing. |
| `DELETE` | `/portfolios/{id}` | — | `204`. Cascades to holdings. `404` if missing. |
| `POST` | `/portfolios/{id}/holdings` | `{coin_symbol, quantity, average_buy_price}` | `201`. `404` if the portfolio is missing; `400` if `coin_symbol` has no current warehouse snapshot or the portfolio already holds it; `422` for non-positive `quantity` or negative `average_buy_price`. |
| `PUT` | `/holdings/{id}` | `{quantity, average_buy_price}` | Coin is fixed once created. `404` if missing. |
| `DELETE` | `/holdings/{id}` | — | `204`. `404` if missing. |

### Holding response shape

```json
{
  "id": 1,
  "portfolio_id": 1,
  "coin_symbol": "BTC",
  "coin_name": "Bitcoin",
  "quantity": 1.5,
  "average_buy_price": 20000.0,
  "current_price": 65598.0,
  "current_value": 98397.0,
  "cost_basis": 30000.0,
  "unrealized_profit": 68397.0,
  "profit_percent": 227.99,
  "created_at": "2026-07-23T11:32:50.707217Z",
  "updated_at": "2026-07-23T11:32:50.707217Z"
}
```

`current_price`/`current_value`/`unrealized_profit`/`profit_percent` are `null` when the coin has
since dropped out of the tracked warehouse snapshot; `cost_basis` is always computable.

## Error shape

Non-2xx responses use FastAPI's standard shape. Most errors are a plain string:

```json
{"detail": "Portfolio 999 not found"}
```

`422` validation errors use Pydantic's list-of-objects shape:

```json
{"detail": [{"type": "less_than_equal", "loc": ["query", "limit"], "msg": "Input should be less than or equal to 500", "input": "99999", "ctx": {"le": 500}}]}
```

The frontend's `api/client.ts` (`detailFor`) handles both shapes uniformly when surfacing error
messages to the user.

## CORS

Allowed origins default to the Vite dev server (`http://localhost:5173`,
`http://127.0.0.1:5173`) and are configurable via `CORS_ALLOWED_ORIGINS` (comma-separated) — see
[PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md).
