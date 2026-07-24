import argparse
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime

from database import get_connection

PIPELINE_NAME = "coingecko_warehouse_load"
SOURCE_PIPELINE_NAME = "coingecko_market_snapshot"


class ETLError(Exception):
    """Raised when a warehouse-load run fails. The failure is already recorded in audit.etl_run."""

    def __init__(self, run_id: int, message: str) -> None:
        super().__init__(message)
        self.run_id = run_id


@dataclass
class ETLResult:
    etl_run_id: int
    staging_run_id: int
    snapshot_date: date
    dim_date_inserted: int
    dim_coin_inserted: int
    dim_coin_updated: int
    fact_inserted: int
    elapsed_seconds: float


def select_batch(cur, run_id: int | None) -> int | None:
    if run_id is not None:
        cur.execute(
            "SELECT run_id FROM audit.etl_run WHERE run_id = %s AND pipeline_name = %s AND status = 'succeeded'",
            (run_id, SOURCE_PIPELINE_NAME),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"run_id {run_id} is not a succeeded '{SOURCE_PIPELINE_NAME}' batch")
        return row[0]

    cur.execute(
        """
        SELECT run_id FROM audit.etl_run
        WHERE pipeline_name = %s AND status = 'succeeded' AND loaded_at IS NULL
        ORDER BY run_id
        LIMIT 1
        """,
        (SOURCE_PIPELINE_NAME,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def ensure_dim_date(cur, snapshot_date: date) -> bool:
    """Insert dw.dim_date row for snapshot_date if missing. Returns True if inserted."""
    date_key = int(snapshot_date.strftime("%Y%m%d"))
    cur.execute("SELECT 1 FROM dw.dim_date WHERE date_key = %s", (date_key,))
    if cur.fetchone():
        return False

    iso_year, iso_week, iso_weekday = snapshot_date.isocalendar()
    cur.execute(
        """
        INSERT INTO dw.dim_date
            (date_key, full_date, year, quarter, month, month_name, day, day_of_week, day_name, week_of_year, is_weekend)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            date_key,
            snapshot_date,
            snapshot_date.year,
            (snapshot_date.month - 1) // 3 + 1,
            snapshot_date.month,
            snapshot_date.strftime("%B"),
            snapshot_date.day,
            iso_weekday,
            snapshot_date.strftime("%A"),
            iso_week,
            iso_weekday >= 6,
        ),
    )
    return True


def upsert_fact_market_snapshot(
    cur,
    date_key: int,
    coin_key: int,
    price_usd: float,
    market_cap_usd: float | None,
    volume_24h_usd: float | None,
    circulating_supply: float | None,
    market_cap_rank: int | None,
) -> bool:
    """Insert one dw.fact_market_snapshot row, ON CONFLICT (date_key, coin_key) DO NOTHING.

    Returns True if a row was actually inserted. Shared by the live ETL loop (`run_etl`) and the
    historical backfill pipeline (`etl/backfill_market_history.py`) so both write the fact table
    through the exact same grain-level idempotency guard.
    """
    cur.execute(
        """
        INSERT INTO dw.fact_market_snapshot
            (date_key, coin_key, price_usd, market_cap_usd, volume_24h_usd, circulating_supply, market_cap_rank)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (date_key, coin_key) DO NOTHING
        RETURNING fact_key
        """,
        (date_key, coin_key, price_usd, market_cap_usd, volume_24h_usd, circulating_supply, market_cap_rank),
    )
    return cur.fetchone() is not None


def insert_intraday_from_staging(cur, run_id: int, observation_timestamp: datetime) -> int:
    """Part 10: insert one dw.fact_market_intraday row per coin staged by ingestion run `run_id`,
    all sharing the single `observation_timestamp` the caller captured for this run. Reuses the
    exact rows the live ingest step already fetched from CoinGecko in one call -- no second API
    round-trip, unlike etl/ingest_intraday_market_data.py's per-coin /market_chart calls -- so a
    manual "Take New Snapshot" press stays fast.

    ON CONFLICT (coin_key, observation_timestamp) DO NOTHING makes this safe to call more than
    once for the same run_id/timestamp pair. In practice every call passes a freshly-captured
    timestamp, so distinct manual presses always land as distinct intraday rows. Coins with no
    current dw.dim_coin row (should not happen right after upsert_dim_coin has run for this same
    batch) are silently skipped via the INNER JOIN. Returns the number of rows inserted.
    """
    cur.execute(
        """
        INSERT INTO dw.fact_market_intraday
            (coin_key, observation_timestamp, price_usd, market_cap_usd, volume_24h_usd, run_id)
        SELECT dc.coin_key, %s, s.current_price, s.market_cap, s.total_volume, %s
        FROM staging.coingecko_market_snapshot s
        JOIN dw.dim_coin dc ON dc.coin_id = s.coin_id AND dc.is_current
        WHERE s.run_id = %s
        ON CONFLICT (coin_key, observation_timestamp) DO NOTHING
        RETURNING intraday_key
        """,
        (observation_timestamp, run_id, run_id),
    )
    return len(cur.fetchall())


def upsert_dim_coin(
    cur, coin_id: str, symbol: str, name: str, image_url: str | None = None
) -> tuple[int, str]:
    """Insert/expire-and-insert dw.dim_coin as needed. Returns (coin_key, 'inserted'|'updated'|'unchanged').

    `image_url` is intentionally excluded from the SCD2 change-detection that governs
    symbol/name: a logo is a cosmetic attribute, not an identity change, so it never mints a new
    dim_coin version. When a non-None `image_url` differs from what's currently stored, it's
    written with a plain in-place UPDATE instead (see 025_dim_coin_add_image_url.sql).
    `etl/backfill_market_history.py` never has an image_url to offer (its CoinGecko endpoint doesn't
    return one) and passes None, which is a no-op here -- it never blanks out an existing logo.
    """
    cur.execute(
        "SELECT coin_key, symbol, name, image_url FROM dw.dim_coin WHERE coin_id = %s AND is_current",
        (coin_id,),
    )
    current = cur.fetchone()

    if current is None:
        cur.execute(
            "INSERT INTO dw.dim_coin (coin_id, symbol, name, image_url) VALUES (%s, %s, %s, %s) RETURNING coin_key",
            (coin_id, symbol, name, image_url),
        )
        return cur.fetchone()[0], "inserted"

    coin_key, current_symbol, current_name, current_image_url = current

    if image_url is not None and image_url != current_image_url:
        cur.execute("UPDATE dw.dim_coin SET image_url = %s WHERE coin_key = %s", (image_url, coin_key))

    if current_symbol == symbol and current_name == name:
        return coin_key, "unchanged"

    cur.execute(
        "UPDATE dw.dim_coin SET valid_to = now(), is_current = false WHERE coin_key = %s",
        (coin_key,),
    )
    cur.execute(
        "INSERT INTO dw.dim_coin (coin_id, symbol, name, image_url) VALUES (%s, %s, %s, %s) RETURNING coin_key",
        (coin_id, symbol, name, image_url if image_url is not None else current_image_url),
    )
    return cur.fetchone()[0], "updated"


def start_etl_run(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO audit.etl_run (pipeline_name, status) VALUES (%s, 'running') RETURNING run_id",
            (PIPELINE_NAME,),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def finish_etl_run(conn, run_id: int, status: str, rows_processed: int, error_message: str | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE audit.etl_run
            SET status = %s, finished_at = now(), rows_processed = %s, error_message = %s
            WHERE run_id = %s
            """,
            (status, rows_processed, error_message, run_id),
        )
    conn.commit()


def run_etl(conn, run_id: int | None = None) -> ETLResult | None:
    """Load one staged CoinGecko batch into the warehouse, recording an audit.etl_run row.

    Reusable entry point shared by the CLI (`main`) and the scheduler/admin endpoint.
    Returns None if there is no batch to process. Raises ValueError if an explicit `run_id`
    does not reference a succeeded staging batch, or ETLError (with the failed run_id already
    recorded) if the load itself fails.
    """
    with conn.cursor() as cur:
        batch_run_id = select_batch(cur, run_id)

    if batch_run_id is None:
        return None

    started = time.monotonic()
    etl_run_id = start_etl_run(conn)

    dim_date_inserted = 0
    dim_coin_inserted = 0
    dim_coin_updated = 0
    fact_inserted = 0
    snapshot_date = None

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT started_at FROM audit.etl_run WHERE run_id = %s", (batch_run_id,))
            snapshot_date = cur.fetchone()[0].date()

            dim_date_inserted = 1 if ensure_dim_date(cur, snapshot_date) else 0
            date_key = int(snapshot_date.strftime("%Y%m%d"))

            cur.execute(
                """
                SELECT coin_id, symbol, name, current_price, market_cap, market_cap_rank, total_volume,
                       circulating_supply, image_url
                FROM staging.coingecko_market_snapshot
                WHERE run_id = %s
                """,
                (batch_run_id,),
            )
            staged_rows = cur.fetchall()

            for coin_id, symbol, name, price, market_cap, rank, volume, supply, image_url in staged_rows:
                coin_key, action = upsert_dim_coin(cur, coin_id, symbol, name, image_url)
                if action == "inserted":
                    dim_coin_inserted += 1
                elif action == "updated":
                    dim_coin_updated += 1

                if upsert_fact_market_snapshot(cur, date_key, coin_key, price, market_cap, volume, supply, rank):
                    fact_inserted += 1

            cur.execute("UPDATE audit.etl_run SET loaded_at = now() WHERE run_id = %s", (batch_run_id,))

        conn.commit()
    except Exception as exc:
        conn.rollback()
        finish_etl_run(conn, etl_run_id, "failed", 0, str(exc))
        raise ETLError(etl_run_id, str(exc)) from exc

    elapsed = time.monotonic() - started
    finish_etl_run(conn, etl_run_id, "succeeded", fact_inserted, None)

    return ETLResult(
        etl_run_id=etl_run_id,
        staging_run_id=batch_run_id,
        snapshot_date=snapshot_date,
        dim_date_inserted=dim_date_inserted,
        dim_coin_inserted=dim_coin_inserted,
        dim_coin_updated=dim_coin_updated,
        fact_inserted=fact_inserted,
        elapsed_seconds=elapsed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Load one staged CoinGecko batch into the data warehouse.")
    parser.add_argument(
        "--run-id",
        type=int,
        default=None,
        help="Specific staging batch to load (default: oldest unloaded succeeded batch)",
    )
    args = parser.parse_args()

    conn = get_connection()

    try:
        result = run_etl(conn, run_id=args.run_id)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ETLError as exc:
        print(f"ETL run {exc.run_id} failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    if result is None:
        print("No new batches to process.")
        return 0

    print(f"Batch processed: staging run_id={result.staging_run_id} (snapshot date {result.snapshot_date})")
    print(f"  dim_date rows inserted:       {result.dim_date_inserted}")
    print(f"  dim_coin rows inserted:       {result.dim_coin_inserted}")
    print(f"  dim_coin rows updated (SCD2): {result.dim_coin_updated}")
    print(f"  fact rows inserted:           {result.fact_inserted}")
    print(f"  elapsed: {result.elapsed_seconds:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
