import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import timedelta, timezone, datetime

from integrations.coingecko import CoinGeckoAPIError, CoinIntradayObservation, fetch_coin_market_chart
from database import get_connection
from utils.logging_config import get_logger

"""Intraday ingestion: loads real, sub-daily CoinGecko market data for a configurable coin list
into `dw.fact_market_intraday` -- a separate fact table from `dw.fact_market_snapshot`, kept
distinct on purpose (see that table's migration comment) so intraday observations never have to
be squeezed into the daily `(date_key, coin_key)` grain.

Uses `/coins/{id}/market_chart?days=1`, the only free, keyless CoinGecko endpoint that returns
multiple observations for the current day. Idempotent via `ON CONFLICT (coin_key,
observation_timestamp) DO NOTHING`; re-running the same command only adds observations CoinGecko
has newly reported, same resumability spirit as `etl/backfill_market_history.py`.

Requires each coin to already have a current `dw.dim_coin` row (populated by the live top-100
ingestion pipeline) -- `/market_chart` doesn't echo back symbol/name, so there is nothing to
upsert a dimension row from here.
"""

PIPELINE_NAME = "coingecko_intraday_ingest"
DEFAULT_REQUEST_DELAY_SECONDS = 2.0
DEFAULT_MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 2.0
DEFAULT_RETENTION_DAYS = 2

logger = get_logger("ingest_intraday_market_data")


@dataclass
class IntradaySummary:
    run_id: int
    coins: list[str]
    observations_loaded: int = 0
    observations_skipped: int = 0
    coins_failed: list[str] = field(default_factory=list)
    pruned_rows: int = 0
    elapsed_seconds: float = 0.0


def get_current_coin_key(cur, coin_id: str) -> int | None:
    """Look up the coin's current dw.dim_coin surrogate key. Returns None if the coin isn't
    tracked yet -- intraday ingestion never creates dim_coin rows itself."""
    cur.execute("SELECT coin_key FROM dw.dim_coin WHERE coin_id = %s AND is_current", (coin_id,))
    row = cur.fetchone()
    return row[0] if row else None


def fetch_with_retry(coin_id: str, days: int, max_retries: int) -> list[CoinIntradayObservation]:
    delay = RETRY_BASE_DELAY_SECONDS
    last_error: CoinGeckoAPIError | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return fetch_coin_market_chart(coin_id, days=days)
        except CoinGeckoAPIError as exc:
            last_error = exc
            if attempt < max_retries:
                logger.warning(
                    "Attempt %d/%d failed for %s: %s (retrying in %.0fs)",
                    attempt,
                    max_retries,
                    coin_id,
                    exc,
                    delay,
                )
                time.sleep(delay)
                delay *= 2
    assert last_error is not None
    raise last_error


def load_observations(conn, coin_key: int, observations: list[CoinIntradayObservation]) -> tuple[int, int]:
    """Insert observations for one coin, ON CONFLICT (coin_key, observation_timestamp) DO NOTHING.
    Returns (inserted, skipped). Commits immediately so a later coin's failure never rolls back
    an earlier coin's already-loaded observations."""
    inserted = 0
    skipped = 0
    with conn.cursor() as cur:
        for obs in observations:
            cur.execute(
                """
                INSERT INTO dw.fact_market_intraday
                    (coin_key, observation_timestamp, price_usd, market_cap_usd, volume_24h_usd)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (coin_key, observation_timestamp) DO NOTHING
                RETURNING intraday_key
                """,
                (coin_key, obs.observation_timestamp, obs.price_usd, obs.market_cap_usd, obs.volume_24h_usd),
            )
            if cur.fetchone() is not None:
                inserted += 1
            else:
                skipped += 1
    conn.commit()
    return inserted, skipped


def prune_old_intraday(conn, retention_days: int) -> int:
    """Delete intraday observations older than `retention_days`. This table exists only to power
    the "Today" chart, not long-term trend analysis (that's what the daily warehouse grain is
    for), so it doesn't need to grow unbounded. Returns the number of rows deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dw.fact_market_intraday WHERE observation_timestamp < %s", (cutoff,))
        deleted = cur.rowcount
    conn.commit()
    return deleted


def run_intraday_ingest(
    conn,
    coins: list[str],
    days: int = 1,
    request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retention_days: int | None = DEFAULT_RETENTION_DAYS,
) -> IntradaySummary:
    """Reusable entry point (CLI-independent, unit-testable): ingests `/market_chart` intraday
    observations for every coin in `coins`, recording one audit.etl_run row for the invocation."""
    started = time.monotonic()

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO audit.etl_run (pipeline_name, status) VALUES (%s, 'running') RETURNING run_id",
            (PIPELINE_NAME,),
        )
        run_id = cur.fetchone()[0]
    conn.commit()

    summary = IntradaySummary(run_id=run_id, coins=coins)

    for coin_id in coins:
        with conn.cursor() as cur:
            coin_key = get_current_coin_key(cur, coin_id)

        if coin_key is None:
            logger.error("Skipping %s: no current dw.dim_coin row (coin not yet tracked)", coin_id)
            summary.coins_failed.append(coin_id)
            continue

        try:
            observations = fetch_with_retry(coin_id, days, max_retries)
        except CoinGeckoAPIError as exc:
            logger.error("Giving up on %s after %d attempts: %s", coin_id, max_retries, exc)
            summary.coins_failed.append(coin_id)
            time.sleep(request_delay_seconds)
            continue

        inserted, skipped = load_observations(conn, coin_key, observations)
        summary.observations_loaded += inserted
        summary.observations_skipped += skipped
        logger.info(
            "Loaded %s: %d new observation(s), %d already present",
            coin_id,
            inserted,
            skipped,
        )
        time.sleep(request_delay_seconds)

    if retention_days is not None:
        summary.pruned_rows = prune_old_intraday(conn, retention_days)

    summary.elapsed_seconds = time.monotonic() - started

    status = "failed" if summary.observations_loaded == 0 and summary.coins_failed and len(summary.coins_failed) == len(coins) else "succeeded"
    error_message = None
    if summary.coins_failed:
        error_message = f"{len(summary.coins_failed)} of {len(coins)} coin(s) failed: {', '.join(summary.coins_failed)}"

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE audit.etl_run
            SET status = %s, finished_at = now(), rows_processed = %s, error_message = %s
            WHERE run_id = %s
            """,
            (status, summary.observations_loaded, error_message, run_id),
        )
    conn.commit()

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest real intraday CoinGecko market data into dw.fact_market_intraday."
    )
    parser.add_argument(
        "--coins", required=True, help="Comma-separated CoinGecko coin ids, e.g. bitcoin,ethereum,solana"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="CoinGecko market_chart 'days' window (default 1, i.e. today's intraday granularity).",
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=DEFAULT_REQUEST_DELAY_SECONDS,
        help=f"Delay between CoinGecko calls (default {DEFAULT_REQUEST_DELAY_SECONDS}).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Retry attempts per coin before giving up (default {DEFAULT_MAX_RETRIES}).",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Delete intraday observations older than this many days after loading (default {DEFAULT_RETENTION_DAYS}). Use -1 to disable pruning.",
    )
    args = parser.parse_args()

    coins = [c.strip() for c in args.coins.split(",") if c.strip()]
    if not coins:
        print("Error: --coins must list at least one CoinGecko coin id", file=sys.stderr)
        return 1

    retention_days = None if args.retention_days < 0 else args.retention_days

    print(f"Ingesting intraday data for {len(coins)} coin(s): {', '.join(coins)}")

    conn = get_connection()
    try:
        summary = run_intraday_ingest(
            conn,
            coins,
            days=args.days,
            request_delay_seconds=args.request_delay_seconds,
            max_retries=args.max_retries,
            retention_days=retention_days,
        )
    finally:
        conn.close()

    print()
    print(f"Intraday ingest run {summary.run_id} complete in {summary.elapsed_seconds:.1f}s")
    print(f"  observations loaded:  {summary.observations_loaded}")
    print(f"  observations skipped (already loaded): {summary.observations_skipped}")
    if summary.pruned_rows:
        print(f"  pruned rows older than retention window: {summary.pruned_rows}")
    if summary.coins_failed:
        print(f"  coins failed: {', '.join(summary.coins_failed)}")

    return 1 if summary.observations_loaded == 0 and len(summary.coins_failed) == len(coins) else 0


if __name__ == "__main__":
    sys.exit(main())
