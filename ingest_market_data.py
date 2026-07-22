import argparse
import sys

from coingecko import CoinGeckoAPIError, fetch_top_markets
from database import get_connection
from staging_repository import insert_market_snapshots

PIPELINE_NAME = "coingecko_market_snapshot"


def start_run(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO audit.etl_run (pipeline_name, status) VALUES (%s, 'running') RETURNING run_id",
            (PIPELINE_NAME,),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def finish_run(conn, run_id: int, status: str, rows_processed: int, error_message: str | None) -> None:
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
    parser = argparse.ArgumentParser(description="Ingest current CoinGecko market data into the staging layer.")
    parser.add_argument("--currency", default="usd", help="Quote currency (default: usd)")
    parser.add_argument("--limit", type=int, default=100, help="Number of coins to fetch (default: 100)")
    parser.add_argument("--order", default="market_cap_desc", help="CoinGecko ordering (default: market_cap_desc)")
    args = parser.parse_args()

    conn = get_connection()
    run_id = start_run(conn)
    print(f"Started run {run_id} ({PIPELINE_NAME})")

    try:
        coins = fetch_top_markets(vs_currency=args.currency, limit=args.limit, order=args.order)
    except CoinGeckoAPIError as exc:
        finish_run(conn, run_id, "failed", rows_processed=0, error_message=str(exc))
        conn.close()
        print(f"Run {run_id} failed: {exc}", file=sys.stderr)
        return 1

    try:
        rows_inserted = insert_market_snapshots(conn, run_id, coins)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        finish_run(conn, run_id, "failed", rows_processed=0, error_message=str(exc))
        conn.close()
        print(f"Run {run_id} failed while inserting staging rows: {exc}", file=sys.stderr)
        return 1

    finish_run(conn, run_id, "succeeded", rows_processed=rows_inserted, error_message=None)
    conn.close()

    print(f"Run {run_id} succeeded: inserted {rows_inserted} rows into staging.coingecko_market_snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
