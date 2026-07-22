import argparse
import sys
import time
from datetime import date

from database import get_connection

PIPELINE_NAME = "coingecko_warehouse_load"
SOURCE_PIPELINE_NAME = "coingecko_market_snapshot"


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


def upsert_dim_coin(cur, coin_id: str, symbol: str, name: str) -> tuple[int, str]:
    """Insert/expire-and-insert dw.dim_coin as needed. Returns (coin_key, 'inserted'|'updated'|'unchanged')."""
    cur.execute(
        "SELECT coin_key, symbol, name FROM dw.dim_coin WHERE coin_id = %s AND is_current",
        (coin_id,),
    )
    current = cur.fetchone()

    if current is None:
        cur.execute(
            "INSERT INTO dw.dim_coin (coin_id, symbol, name) VALUES (%s, %s, %s) RETURNING coin_key",
            (coin_id, symbol, name),
        )
        return cur.fetchone()[0], "inserted"

    coin_key, current_symbol, current_name = current
    if current_symbol == symbol and current_name == name:
        return coin_key, "unchanged"

    cur.execute(
        "UPDATE dw.dim_coin SET valid_to = now(), is_current = false WHERE coin_key = %s",
        (coin_key,),
    )
    cur.execute(
        "INSERT INTO dw.dim_coin (coin_id, symbol, name) VALUES (%s, %s, %s) RETURNING coin_key",
        (coin_id, symbol, name),
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

    with conn.cursor() as cur:
        try:
            batch_run_id = select_batch(cur, args.run_id)
        except ValueError as exc:
            conn.close()
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if batch_run_id is None:
        print("No new batches to process.")
        conn.close()
        return 0

    started = time.monotonic()
    etl_run_id = start_etl_run(conn)
    print(f"Started ETL run {etl_run_id} ({PIPELINE_NAME}) for staging batch {batch_run_id}")

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
                SELECT coin_id, symbol, name, current_price, market_cap, market_cap_rank, total_volume, circulating_supply
                FROM staging.coingecko_market_snapshot
                WHERE run_id = %s
                """,
                (batch_run_id,),
            )
            staged_rows = cur.fetchall()

            for coin_id, symbol, name, price, market_cap, rank, volume, supply in staged_rows:
                coin_key, action = upsert_dim_coin(cur, coin_id, symbol, name)
                if action == "inserted":
                    dim_coin_inserted += 1
                elif action == "updated":
                    dim_coin_updated += 1

                cur.execute(
                    """
                    INSERT INTO dw.fact_market_snapshot
                        (date_key, coin_key, price_usd, market_cap_usd, volume_24h_usd, circulating_supply, market_cap_rank)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date_key, coin_key) DO NOTHING
                    RETURNING fact_key
                    """,
                    (date_key, coin_key, price, market_cap, volume, supply, rank),
                )
                if cur.fetchone() is not None:
                    fact_inserted += 1

            cur.execute("UPDATE audit.etl_run SET loaded_at = now() WHERE run_id = %s", (batch_run_id,))

        conn.commit()
    except Exception as exc:
        conn.rollback()
        finish_etl_run(conn, etl_run_id, "failed", 0, str(exc))
        conn.close()
        print(f"ETL run {etl_run_id} failed: {exc}", file=sys.stderr)
        return 1

    elapsed = time.monotonic() - started
    finish_etl_run(conn, etl_run_id, "succeeded", fact_inserted, None)
    conn.close()

    print(f"Batch processed: staging run_id={batch_run_id} (snapshot date {snapshot_date})")
    print(f"  dim_date rows inserted:       {dim_date_inserted}")
    print(f"  dim_coin rows inserted:       {dim_coin_inserted}")
    print(f"  dim_coin rows updated (SCD2): {dim_coin_updated}")
    print(f"  fact rows inserted:           {fact_inserted}")
    print(f"  elapsed: {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
