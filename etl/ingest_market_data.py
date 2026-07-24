import argparse
import sys
from dataclasses import dataclass

from integrations.coingecko import CoinGeckoAPIError, fetch_top_markets
from database import get_connection
from etl.staging_repository import insert_market_snapshots

PIPELINE_NAME = "coingecko_market_snapshot"


class IngestError(Exception):
    """Raised when a staging ingest run fails. The failure is already recorded in audit.etl_run."""

    def __init__(self, run_id: int, message: str) -> None:
        super().__init__(message)
        self.run_id = run_id


@dataclass
class IngestResult:
    run_id: int
    rows_inserted: int


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


def run_ingest(conn, currency: str = "usd", limit: int = 100, order: str = "market_cap_desc") -> IngestResult:
    """Fetch current CoinGecko market data and stage it, recording an audit.etl_run row.

    Reusable entry point shared by the CLI (`main`) and the scheduler/admin endpoint.
    Raises IngestError (with the failed run_id already recorded) on any failure.
    """
    run_id = start_run(conn)

    try:
        coins = fetch_top_markets(vs_currency=currency, limit=limit, order=order)
    except CoinGeckoAPIError as exc:
        finish_run(conn, run_id, "failed", rows_processed=0, error_message=str(exc))
        raise IngestError(run_id, str(exc)) from exc

    try:
        rows_inserted = insert_market_snapshots(conn, run_id, coins)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        finish_run(conn, run_id, "failed", rows_processed=0, error_message=str(exc))
        raise IngestError(run_id, str(exc)) from exc

    finish_run(conn, run_id, "succeeded", rows_processed=rows_inserted, error_message=None)
    return IngestResult(run_id=run_id, rows_inserted=rows_inserted)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest current CoinGecko market data into the staging layer.")
    parser.add_argument("--currency", default="usd", help="Quote currency (default: usd)")
    parser.add_argument("--limit", type=int, default=100, help="Number of coins to fetch (default: 100)")
    parser.add_argument("--order", default="market_cap_desc", help="CoinGecko ordering (default: market_cap_desc)")
    args = parser.parse_args()

    conn = get_connection()
    try:
        result = run_ingest(conn, currency=args.currency, limit=args.limit, order=args.order)
    except IngestError as exc:
        print(f"Run {exc.run_id} failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(
        f"Run {result.run_id} succeeded: inserted {result.rows_inserted} rows "
        "into staging.coingecko_market_snapshot"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
