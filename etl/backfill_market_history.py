import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta

from integrations.coingecko import CoinGeckoAccessRestrictedError, CoinGeckoAPIError, CoinHistorySnapshot, fetch_coin_history
from database import get_connection
from etl.load_warehouse import ensure_dim_date, upsert_dim_coin, upsert_fact_market_snapshot
from utils.logging_config import get_logger

"""Historical backfill: loads real, per-day CoinGecko market data for a configurable coin list
and date range into the same dw.fact_market_snapshot grain the live pipeline writes to.

Uses `/coins/{id}/history` (one exact calendar day per call) rather than `/market_chart/range`,
because the free, keyless range endpoint returns no market_cap_rank/circulating_supply and an
auto-selected granularity that doesn't line up with the daily (date_key, coin_key) fact grain.
The cost is one CoinGecko call per (coin, day) pair, which is why this script rate-limits and
retries explicitly instead of firing requests as fast as possible.

Resumable by construction: before spending an API call, each (coin, date) pair is checked
against the warehouse and skipped if already loaded, and every pair that *is* loaded is
committed immediately (not batched into one giant transaction) — re-running the same command
after an interruption only fetches what's still missing.
"""

PIPELINE_NAME = "coingecko_history_backfill"
DEFAULT_REQUEST_DELAY_SECONDS = 1.5
DEFAULT_MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 2.0

logger = get_logger("backfill_market_history")


@dataclass
class BackfillSummary:
    run_id: int
    coins: list[str]
    start_date: date
    end_date: date
    dates_skipped: int = 0
    dates_loaded: int = 0
    dates_failed: int = 0
    failed_pairs: list[tuple[str, date]] = field(default_factory=list)
    elapsed_seconds: float = 0.0


def daterange(start: date, end: date):
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)


def fact_exists(conn, coin_id: str, on_date: date) -> bool:
    """True if any (coin_id, on_date) fact row is already loaded, across any dim_coin SCD2
    version — checked before calling CoinGecko so a resumed run spends zero API calls on days
    that already succeeded."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM dw.fact_market_snapshot f
            JOIN dw.dim_coin c ON c.coin_key = f.coin_key
            JOIN dw.dim_date d ON d.date_key = f.date_key
            WHERE c.coin_id = %s AND d.full_date = %s
            LIMIT 1
            """,
            (coin_id, on_date),
        )
        return cur.fetchone() is not None


def fetch_with_retry(coin_id: str, on_date: date, max_retries: int) -> CoinHistorySnapshot | None:
    """Returns the snapshot, or None if CoinGecko genuinely has no data for that day (e.g. the
    coin didn't exist yet). Raises CoinGeckoAPIError once every retry attempt has failed.

    CoinGeckoAccessRestrictedError (HTTP 401/403 — the free tier's history window boundary) is
    deliberately *not* retried: it's a permanent rejection of this exact request, so retrying
    would only waste attempts and rate-limit budget on something that can never succeed.
    """
    delay = RETRY_BASE_DELAY_SECONDS
    last_error: CoinGeckoAPIError | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return fetch_coin_history(coin_id, on_date)
        except CoinGeckoAccessRestrictedError:
            raise
        except CoinGeckoAPIError as exc:
            last_error = exc
            if attempt < max_retries:
                logger.warning(
                    "Attempt %d/%d failed for %s on %s: %s (retrying in %.0fs)",
                    attempt,
                    max_retries,
                    coin_id,
                    on_date,
                    exc,
                    delay,
                )
                time.sleep(delay)
                delay *= 2
    assert last_error is not None
    raise last_error


def load_one_day(conn, run_id: int, coin_id: str, on_date: date, snapshot: CoinHistorySnapshot) -> bool:
    """Land one backfilled (coin, date) pair in staging, then load it into the warehouse through
    the exact same dim_date/dim_coin/fact helpers the live ETL uses, and commit immediately."""
    date_key = int(on_date.strftime("%Y%m%d"))
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO staging.coingecko_coin_history
                (run_id, coin_id, symbol, name, snapshot_date, current_price, market_cap, total_volume, market_cap_rank)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (coin_id, snapshot_date) DO NOTHING
            """,
            (
                run_id,
                coin_id,
                snapshot.symbol,
                snapshot.name,
                on_date,
                snapshot.current_price,
                snapshot.market_cap,
                snapshot.total_volume,
                snapshot.market_cap_rank,
            ),
        )
        ensure_dim_date(cur, on_date)
        coin_key, _ = upsert_dim_coin(cur, coin_id, snapshot.symbol, snapshot.name)
        inserted = upsert_fact_market_snapshot(
            cur,
            date_key,
            coin_key,
            snapshot.current_price,
            snapshot.market_cap,
            snapshot.total_volume,
            None,  # circulating_supply: not reported by /coins/{id}/history
            snapshot.market_cap_rank,
        )
    conn.commit()
    return inserted


def run_backfill(
    conn,
    coins: list[str],
    start_date: date,
    end_date: date,
    request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> BackfillSummary:
    """Reusable entry point (CLI-independent, so it's directly unit-testable): backfills every
    (coin, date) pair in `coins` x [start_date, end_date], recording one audit.etl_run row for
    the whole invocation."""
    started = time.monotonic()

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO audit.etl_run (pipeline_name, status) VALUES (%s, 'running') RETURNING run_id",
            (PIPELINE_NAME,),
        )
        run_id = cur.fetchone()[0]
    conn.commit()

    summary = BackfillSummary(run_id=run_id, coins=coins, start_date=start_date, end_date=end_date)

    for coin_id in coins:
        for on_date in daterange(start_date, end_date):
            if fact_exists(conn, coin_id, on_date):
                summary.dates_skipped += 1
                continue

            try:
                snapshot = fetch_with_retry(coin_id, on_date, max_retries)
            except CoinGeckoAccessRestrictedError as exc:
                logger.error("CoinGecko rejected %s on %s (outside allowed history window): %s", coin_id, on_date, exc)
                summary.dates_failed += 1
                summary.failed_pairs.append((coin_id, on_date))
                time.sleep(request_delay_seconds)
                continue
            except CoinGeckoAPIError as exc:
                logger.error("Giving up on %s for %s after %d attempts: %s", coin_id, on_date, max_retries, exc)
                summary.dates_failed += 1
                summary.failed_pairs.append((coin_id, on_date))
                time.sleep(request_delay_seconds)
                continue

            time.sleep(request_delay_seconds)

            if snapshot is None:
                logger.info("No CoinGecko data for %s on %s (likely predates listing); skipping", coin_id, on_date)
                summary.dates_skipped += 1
                continue

            if load_one_day(conn, run_id, coin_id, on_date, snapshot):
                summary.dates_loaded += 1
                logger.info("Loaded %s %s: $%.2f", coin_id, on_date, snapshot.current_price)
            else:
                summary.dates_skipped += 1

    summary.elapsed_seconds = time.monotonic() - started

    status = "failed" if summary.dates_loaded == 0 and summary.dates_failed > 0 else "succeeded"
    error_message = None
    if summary.failed_pairs:
        pairs = ", ".join(f"{c}@{d}" for c, d in summary.failed_pairs[:20])
        error_message = (
            f"{len(summary.failed_pairs)} of "
            f"{summary.dates_loaded + summary.dates_failed} attempted (coin, date) pairs failed "
            f"after {max_retries} retries: {pairs}"
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE audit.etl_run
            SET status = %s, finished_at = now(), rows_processed = %s, error_message = %s
            WHERE run_id = %s
            """,
            (status, summary.dates_loaded, error_message, run_id),
        )
    conn.commit()

    return summary


def _parse_date_range(args: argparse.Namespace) -> tuple[date, date]:
    if args.days is not None and (args.start_date or args.end_date):
        raise SystemExit("--days is mutually exclusive with --start-date/--end-date")

    if args.days is not None:
        if args.days < 1:
            raise SystemExit("--days must be >= 1")
        end = date.today()
        start = end - timedelta(days=args.days - 1)
        return start, end

    if not args.start_date or not args.end_date:
        raise SystemExit("Provide either --days, or both --start-date and --end-date")

    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    if start > end:
        raise SystemExit("--start-date must not be later than --end-date")
    return start, end


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill real historical CoinGecko market data into the data warehouse."
    )
    parser.add_argument("--days", type=int, default=None, help="Number of days ending today to backfill.")
    parser.add_argument("--start-date", default=None, help="Explicit start date (YYYY-MM-DD). Pairs with --end-date.")
    parser.add_argument("--end-date", default=None, help="Explicit end date (YYYY-MM-DD). Pairs with --start-date.")
    parser.add_argument(
        "--coins", required=True, help="Comma-separated CoinGecko coin ids, e.g. bitcoin,ethereum,solana"
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=DEFAULT_REQUEST_DELAY_SECONDS,
        help=f"Delay between CoinGecko calls, to respect rate limits (default {DEFAULT_REQUEST_DELAY_SECONDS}).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Retry attempts per (coin, date) pair before giving up on it (default {DEFAULT_MAX_RETRIES}).",
    )
    args = parser.parse_args()

    start_date, end_date = _parse_date_range(args)
    coins = [c.strip() for c in args.coins.split(",") if c.strip()]
    if not coins:
        print("Error: --coins must list at least one CoinGecko coin id", file=sys.stderr)
        return 1

    total_days = (end_date - start_date).days + 1
    print(f"Backfilling {len(coins)} coin(s) x {total_days} day(s) = up to {len(coins) * total_days} CoinGecko calls")
    print(f"  coins: {', '.join(coins)}")
    print(f"  range: {start_date} .. {end_date}")
    print()

    conn = get_connection()
    try:
        summary = run_backfill(
            conn,
            coins,
            start_date,
            end_date,
            request_delay_seconds=args.request_delay_seconds,
            max_retries=args.max_retries,
        )
    finally:
        conn.close()

    print()
    print(f"Backfill run {summary.run_id} complete in {summary.elapsed_seconds:.1f}s")
    print(f"  dates loaded:  {summary.dates_loaded}")
    print(f"  dates skipped (already loaded or no CoinGecko data): {summary.dates_skipped}")
    print(f"  dates failed:  {summary.dates_failed}")
    if summary.failed_pairs:
        print("  failures:")
        for coin_id, on_date in summary.failed_pairs:
            print(f"    {coin_id} @ {on_date}")

    return 1 if summary.dates_loaded == 0 and summary.dates_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
