# Milestone: PostgreSQL Connection Foundation

## Plan

Add a `postgres:16` service via `docker-compose.yml` with a named volume and health check, `.env.example` for the connection settings (real `.env` stays gitignored), the minimum client dependency (`psycopg[binary]`, no SQLAlchemy), a one-function `database.py`, and a `GET /health/database` endpoint doing `SELECT 1`. Also untrack `.idea/` from git per the request, without touching the files on disk.

## Files created / modified

| File | Purpose |
|---|---|
| `docker-compose.yml` | Single `postgres:16` service, named volume `pgdata` for persistence, `pg_isready` health check, credentials from `.env`. |
| `.env.example` | Template for `POSTGRES_HOST/PORT/DB/USER/PASSWORD` — used by both the container and the Python client. |
| `.env` | Local, untracked copy of the above with working dev credentials (not committed — already covered by `.gitignore`). |
| `requirements.txt` | Added `psycopg[binary]==3.3.4` (direct Postgres driver, binary wheel, no SQLAlchemy) and `python-dotenv==1.2.2` (loads `.env`). |
| `database.py` | New file. One function, `get_connection()`, returning a `psycopg.Connection` built from env vars. |
| `main.py` | Added `GET /health/database`, which opens a connection, runs `SELECT 1`, and returns `{"status": "healthy"}` or a `503` on failure. `GET /health` unchanged. |
| `README.md` | Replaced with exact commands: env setup, start Postgres, install deps, start FastAPI, test both endpoints. |
| `.idea/` (git index only) | Untracked via `git rm -r --cached -f .idea` — local PyCharm files untouched, confirmed present on disk after. |

## Verification

- `docker compose up -d` → container `cryptomarketwarehouse-postgres` created, volume `cryptomarketwarehouse_pgdata` created.
- Waited for Docker health check → status `healthy`.
- Ran `uvicorn main:app --port 8000` and called both endpoints:
  - `GET /health` → `200 {"status":"healthy"}`
  - `GET /health/database` → `200 {"status":"healthy"}` (real `SELECT 1` against the live container)
- Database connection **tested successfully**.

## Commands to reproduce

```
copy .env.example .env
docker compose up -d
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn main:app --reload
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/database
```

## Note

Docker Desktop was not running at the start of this milestone; it was started to allow testing, and the Postgres container is left running after this milestone.
