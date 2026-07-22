# Analytics REST API

## Architecture

```
FastAPI routes (analytics_routes.py)
        │  HTTP concerns only: path/query params, status codes, response_model,
        │  OpenAPI summaries/descriptions, DB-failure -> 503 mapping
        ▼
Repository (analytics_repository.py)
        │  All SQL lives here, fully parameterized, reads analytics.* views only
        ▼
analytics.* views (pre-existing)
   latest_snapshot, current_market_overview, top_market_cap, top_volume, market_history
```

**Responsibility split**

- **Analytics SQL (existing views)** — owns all joins/aggregation against `dw.*`. The API layer never touches `dw` or `staging`; it only ever does `SELECT ... FROM analytics.<view>`.
- **Repository (`analytics_repository.py`)** — the only module allowed to write SQL strings. Takes a connection and plain Python arguments, returns `dict` rows (via `psycopg.rows.dict_row`). No FastAPI imports — testable independent of HTTP. `ORDER BY` direction is looked up from a fixed `{"asc": "ASC", "desc": "DESC"}` map (`_direction()`), so no request-controlled string is ever interpolated into SQL; all values (dates, limits, symbols) are passed as bind parameters.
- **Response models (`analytics_models.py`)** — typed Pydantic models (`MarketOverview`, `CoinSnapshot`, `TopMarketCapEntry`, `TopVolumeEntry`) defining exactly what the API returns, independent of the DB row shape.
- **API routes (`analytics_routes.py`)** — no SQL at all. Validates/defaults query params, calls the repository, maps rows into response models, and converts outcomes into HTTP semantics:
  - unknown coin symbol → `404`
  - valid symbol / empty result set → `200` + `[]`
  - `from_date > to_date` → `400`
  - `limit` out of `[1, 500]` (or `[1, 1000]` for history) → `422` (automatic, via `Query(ge=..., le=...)`)
  - any DB connection/query failure → `503` (dependency wraps `get_connection()` in try/except, re-raising `HTTPException`s untouched and converting anything else to a clean 503, mirroring the existing `/health/database` pattern)

## Files created

- `analytics_models.py` — Pydantic response models
- `analytics_repository.py` — all analytics SQL (5 read functions + `symbol_has_history` existence check)
- `analytics_routes.py` — `APIRouter` with the 5 endpoints, DB dependency, error handling

## Files modified

- `main.py` — registers `analytics_router`
- `README.md` — added "Analytics REST API" section with endpoint list, query params, and example requests/responses

## Endpoints

| Method | Path | Query params |
|---|---|---|
| GET | `/analytics/overview` | — |
| GET | `/analytics/latest` | `limit`, `order` |
| GET | `/analytics/top-market-cap` | `limit` (default 10), `order` |
| GET | `/analytics/top-volume` | `limit` (default 10), `order` |
| GET | `/analytics/history/{coin_symbol}` | `limit`, `order`, `from_date`, `to_date` |

## Live verification (20 coins loaded, snapshot date 2026-07-22)

All 5 endpoints tested against the running Postgres container:

- `/analytics/overview` → single aggregate object
- `/analytics/latest?limit=3` and `?order=asc` → correctly sorted subsets
- `/analytics/top-market-cap?limit=3` → ranked by market cap, `market_cap_position` intact
- `/analytics/top-volume?limit=3` → ranked by volume, `volume_position` intact
- `/analytics/history/btc?limit=2` and `/analytics/history/BTC` → identical results (case-insensitive match)

Edge cases:
- `/analytics/history/doesnotexist` → `404 {"detail":"Unknown coin symbol: 'doesnotexist'"}`
- `/analytics/history/btc?from_date=2099-01-01` → `200 []` (valid symbol, no rows in range)
- `/analytics/history/btc?from_date=2026-08-01&to_date=2026-01-01` → `400` (inverted range)
- `/analytics/latest?limit=0` → `422` (violates `ge=1`)
- Postgres container stopped mid-test → `/analytics/overview` returned `503 {"detail":"Database unavailable"}` in ~5s; container restarted, endpoint recovered to `200` immediately after healthy again
- `/health` and `/health/database` unaffected throughout

**No-staging-access check**: `grep -n "staging\." analytics_repository.py analytics_routes.py main.py` returns no matches — every query in the repository targets `analytics.*` exclusively (`current_market_overview`, `latest_snapshot`, `top_market_cap`, `top_volume`, `market_history`).

No Git commit was created, per instructions.
