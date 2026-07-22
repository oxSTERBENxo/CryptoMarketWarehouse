# CryptoMarketWarehouse

A crypto analytics platform centered on a PostgreSQL data warehouse. Current milestone: a minimal FastAPI app plus a PostgreSQL connection foundation — no schemas, ingestion, or ETL yet.

## Setup

Copy `.env.example` to `.env` (never commit `.env`):

```
copy .env.example .env
```

## Start PostgreSQL

```
docker compose up -d
```

## Install dependencies

```
.venv\Scripts\pip install -r requirements.txt
```

## Start FastAPI

```
.venv\Scripts\uvicorn main:app --reload
```

## Test both health endpoints

```
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/database
```

Both should return `{"status": "healthy"}`.

## Initialize the database

With PostgreSQL running and dependencies installed:

```
.venv\Scripts\python bootstrap_db.py
```

This runs every SQL script under `db/` in numeric filename order (schemas, then dimensions, then the fact table, then staging, then analytics views), each in its own transaction. It creates the `staging`, `dw`, `audit`, and `analytics` schemas, the initial warehouse tables (`dw.dim_date`, `dw.dim_coin`, `dw.fact_market_snapshot`, `audit.etl_run`), the staging table (`staging.coingecko_market_snapshot`), and the analytics views (below). No data is loaded — ETL into the warehouse is a separate step. The scripts are idempotent, so the command is safe to run again on an already-initialized database.

## Ingest CoinGecko market data into staging

With PostgreSQL running and the database initialized:

```
.venv\Scripts\python ingest_market_data.py
```

Optional flags: `--currency` (default `usd`), `--limit` (default `100`), `--order` (default `market_cap_desc`).

This calls the CoinGecko client, records one batch in `audit.etl_run`, and inserts one row per coin into `staging.coingecko_market_snapshot` in a single transaction. Safe to run repeatedly — each run is a new, independently traceable batch. No warehouse loading happens yet.

## Load a staged batch into the warehouse

With at least one successful ingestion batch in staging:

```
.venv\Scripts\python etl_load_warehouse.py
```

Loads the oldest not-yet-loaded staging batch into `dw.dim_date`, `dw.dim_coin` (SCD Type 2), and `dw.fact_market_snapshot`, all in one transaction, then marks the batch as loaded. Safe to run repeatedly: with no arguments it processes each batch at most once; pass `--run-id <id>` to explicitly reprocess a specific batch, which is also safe since dimension and fact upserts are idempotent by construction.

## Analytical views

`bootstrap_db.py` also creates a set of read-only views in the `analytics` schema, over `dw` only (never `staging`), for future APIs/dashboards to query directly:

- `analytics.latest_snapshot` — one row per coin as of the most recent loaded snapshot date
- `analytics.current_market_overview` — single-row aggregate: coin count, total market cap, total 24h volume
- `analytics.top_market_cap` — latest snapshot ranked by market cap
- `analytics.top_volume` — latest snapshot ranked by 24h volume
- `analytics.market_history` — full historical time series, one row per coin per loaded date

Example:

```
docker compose exec postgres psql -U crypto -d crypto_market_warehouse -c "SELECT * FROM analytics.top_market_cap LIMIT 10;"
```

## Analytics REST API

With PostgreSQL running, the database initialized, and at least one batch loaded into the warehouse, start the API (see "Start FastAPI" above) and query:

- `GET /analytics/overview` — aggregate summary of the latest snapshot
- `GET /analytics/latest` — one row per coin as of the latest snapshot
- `GET /analytics/top-market-cap` — coins ranked by market cap
- `GET /analytics/top-volume` — coins ranked by 24h volume
- `GET /analytics/history/{coin_symbol}` — full historical time series for one coin, matched case-insensitively by symbol

Optional query parameters:

- `limit` — max rows to return (`/latest`, `/top-market-cap`, `/top-volume`, `/history/{coin_symbol}`)
- `order` — `asc` or `desc` (all five list/history endpoints; default `desc` except `/history`, which defaults to `asc` for chronological order)
- `from_date` / `to_date` — bound the date range, `YYYY-MM-DD` (`/history/{coin_symbol}` only)

These endpoints read only from the `analytics` schema — never `staging` or `dw` directly. Interactive docs (with full parameter descriptions) are at `/docs` once the server is running.

### Example requests

```
curl "http://127.0.0.1:8000/analytics/overview"
```
```json
{"snapshot_date":"2026-07-22","coin_count":20,"total_market_cap_usd":2148287214811.0,"total_volume_24h_usd":99354358921.0}
```

```
curl "http://127.0.0.1:8000/analytics/latest?limit=2"
```
```json
[
  {"coin_id":"bitcoin","symbol":"btc","name":"Bitcoin","snapshot_date":"2026-07-22","price_usd":65839.0,"market_cap_usd":1320700595504.0,"volume_24h_usd":28137878848.0,"circulating_supply":20059875.0,"market_cap_rank":1},
  {"coin_id":"ethereum","symbol":"eth","name":"Ethereum","snapshot_date":"2026-07-22","price_usd":1923.61,"market_cap_usd":232150628017.0,"volume_24h_usd":9295355672.0,"circulating_supply":120682775.724111,"market_cap_rank":2}
]
```

```
curl "http://127.0.0.1:8000/analytics/top-market-cap?limit=2"
```
```json
[
  {"market_cap_position":1,"coin_id":"bitcoin","symbol":"btc","name":"Bitcoin","snapshot_date":"2026-07-22","market_cap_usd":1320700595504.0,"price_usd":65839.0},
  {"market_cap_position":2,"coin_id":"ethereum","symbol":"eth","name":"Ethereum","snapshot_date":"2026-07-22","market_cap_usd":232150628017.0,"price_usd":1923.61}
]
```

```
curl "http://127.0.0.1:8000/analytics/top-volume?limit=2"
```
```json
[
  {"volume_position":1,"coin_id":"tether","symbol":"usdt","name":"Tether","snapshot_date":"2026-07-22","volume_24h_usd":45219853534.0,"price_usd":0.999329},
  {"volume_position":2,"coin_id":"bitcoin","symbol":"btc","name":"Bitcoin","snapshot_date":"2026-07-22","volume_24h_usd":28137878848.0,"price_usd":65839.0}
]
```

```
curl "http://127.0.0.1:8000/analytics/history/btc?limit=1"
```
```json
[
  {"coin_id":"bitcoin","symbol":"btc","name":"Bitcoin","snapshot_date":"2026-07-22","price_usd":65839.0,"market_cap_usd":1320700595504.0,"volume_24h_usd":28137878848.0,"circulating_supply":20059875.0,"market_cap_rank":1}
]
```

Unknown symbol (404):

```
curl "http://127.0.0.1:8000/analytics/history/doesnotexist"
```
```json
{"detail":"Unknown coin symbol: 'doesnotexist'"}
```

Valid symbol, no rows in range (200, empty list):

```
curl "http://127.0.0.1:8000/analytics/history/btc?from_date=2099-01-01"
```
```json
[]
```
