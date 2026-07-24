# Backup & Restore

Everything the application owns lives in one PostgreSQL database (`POSTGRES_DB`), across five
schemas: `staging`, `dw`, `audit`, `analytics` (views only — nothing to back up), and `app`
(portfolios). There is no other persistent state — the backend and frontend are stateless
processes.

## Backup

### Logical backup (recommended)

```bash
docker exec cryptomarketwarehouse-postgres pg_dump -U crypto -d crypto_market_warehouse \
  --format=custom --file=/tmp/backup.dump
docker cp cryptomarketwarehouse-postgres:/tmp/backup.dump ./backup-$(date +%Y%m%d).dump
```

(Adjust the container name/user/db to match your `.env`.) `--format=custom` produces a
compressed, `pg_restore`-compatible file and is the recommended format for anything beyond a
throwaway local backup.

If PostgreSQL isn't containerized in your deployment, run `pg_dump` directly against
`POSTGRES_HOST:POSTGRES_PORT`.

### Volume-level backup (Docker Compose only)

`docker-compose.yml` persists PostgreSQL's data directory in the named volume `pgdata`. Backing
up the volume directly is an alternative to `pg_dump` for local/dev use:

```bash
docker run --rm -v cryptomarketwarehouse_pgdata:/data -v "$PWD":/backup alpine \
  tar czf /backup/pgdata-$(date +%Y%m%d).tar.gz -C /data .
```

Stop the `postgres` service first (`docker-compose stop postgres`) for a consistent snapshot — a
volume copy taken while PostgreSQL is running risks capturing a torn write. `pg_dump` (above)
does not have this restriction, since it takes an internally consistent snapshot via a normal
client connection and is the better choice whenever the database needs to stay up.

### What to back up, and how often

- **`app` schema (portfolios/holdings)** is user-entered data that cannot be regenerated —
  back it up like any other primary data store.
- **`staging`/`dw`/`audit`** are all reconstructable by re-running ingestion against CoinGecko,
  but only for dates CoinGecko itself still has data for at the top-N you tracked; anything
  captured historically that has since scrolled out of CoinGecko's current top-N is not
  re-fetchable. Treat the warehouse as authoritative history, not a disposable cache.

## Restore

```bash
# Into a fresh, already-migrated database (run database/bootstrap_db.py first — see LOCAL_DEVELOPMENT.md):
docker exec -i cryptomarketwarehouse-postgres pg_restore -U crypto -d crypto_market_warehouse \
  --clean --if-exists /tmp/backup.dump
```

`pg_restore --clean --if-exists` drops and recreates the objects in the dump before restoring,
so it's safe to run against a database that already has the schema applied via
`database/bootstrap_db.py`. If restoring into a completely empty database instead, `pg_dump --format
=custom` output includes schema DDL, so `pg_restore` alone (without a prior `database/bootstrap_db.py`
run) is also sufficient — `database/bootstrap_db.py` is only needed if you want an empty-but-migrated
database as the baseline (e.g. to restore user data onto a fresh warehouse).

### Point-in-time / disaster recovery

This project does not configure PostgreSQL WAL archiving or point-in-time recovery — the
`docker-compose.yml` setup is a single instance with periodic `pg_dump` as the only backup
strategy described here. For a deployment that needs point-in-time recovery or high availability,
use a managed PostgreSQL service (which typically provides this out of the box) or configure WAL
archiving separately; that setup is outside this document's and the app's current scope — see
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Verifying a backup

Periodically restore a backup into a scratch database and sanity-check it:

```bash
.venv/Scripts/python -c "
import os
os.environ.update(POSTGRES_HOST='localhost', POSTGRES_PORT='5432', POSTGRES_DB='restore_check',
                   POSTGRES_USER='crypto', POSTGRES_PASSWORD='...')
from database import get_connection
with get_connection() as conn, conn.cursor() as cur:
    cur.execute('SELECT count(*) FROM analytics.latest_snapshot')
    print(cur.fetchone())
"
```

A backup that restores but returns zero rows from `analytics.latest_snapshot` is not a usable
backup — verify row counts, not just that `pg_restore` exited `0`.
