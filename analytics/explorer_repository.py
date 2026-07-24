from datetime import date

from psycopg import Connection
from psycopg.rows import dict_row


def fetch_period_stats(conn: Connection, from_date: date, to_date: date) -> list[dict]:
    """Return the full set of per-coin period statistics over [from_date, to_date], computed
    strictly from real observations in analytics.market_history -- one row per qualifying coin.

    This is the single warehouse query behind every Analytics Explorer analysis: the service layer
    filters/sorts these rows in Python per analysis instead of issuing a bespoke query each time.
    Extends the fetch_daily_movers CTE shape (analytics/repository.py) with dollar change, average
    price/volume, first/last observation dates, and start/end market-cap rank -- rank change over
    the period is derivable because analytics.market_history stores CoinGecko's market_cap_rank
    per date. Coins with fewer than 2 observations in range are excluded: a change can't be
    computed (and must never be estimated) from a single point."""
    sql = """
        WITH filtered AS (
            SELECT coin_id, symbol, name, image_url, snapshot_date, price_usd,
                   volume_24h_usd, market_cap_usd, market_cap_rank
            FROM analytics.market_history
            WHERE snapshot_date >= %s AND snapshot_date <= %s
        ),
        bounds AS (
            SELECT coin_id, symbol, name, image_url,
                   MIN(snapshot_date) AS start_date,
                   MAX(snapshot_date) AS end_date,
                   MIN(price_usd) AS low_price,
                   MAX(price_usd) AS high_price,
                   AVG(price_usd) AS avg_price,
                   AVG(volume_24h_usd) AS avg_volume,
                   COUNT(*) AS observation_count
            FROM filtered
            GROUP BY coin_id, symbol, name, image_url
        ),
        first_obs AS (
            SELECT DISTINCT ON (coin_id) coin_id, price_usd AS start_price, market_cap_rank AS start_rank
            FROM filtered ORDER BY coin_id, snapshot_date ASC
        ),
        last_obs AS (
            SELECT DISTINCT ON (coin_id) coin_id, price_usd AS end_price, market_cap_rank AS end_rank,
                   market_cap_usd
            FROM filtered ORDER BY coin_id, snapshot_date DESC
        )
        SELECT
            b.coin_id, b.symbol, b.name, b.image_url,
            b.start_date, b.end_date, b.observation_count,
            f.start_price, l.end_price,
            (l.end_price - f.start_price) AS dollar_change,
            CASE WHEN f.start_price = 0 THEN NULL
                 ELSE (l.end_price - f.start_price) / f.start_price * 100 END AS percent_change,
            b.low_price, b.high_price, b.avg_price, b.avg_volume,
            CASE WHEN b.low_price = 0 THEN NULL
                 ELSE (b.high_price - b.low_price) / b.low_price * 100 END AS volatility_percent,
            f.start_rank, l.end_rank,
            CASE WHEN f.start_rank IS NULL OR l.end_rank IS NULL THEN NULL
                 ELSE f.start_rank - l.end_rank END AS rank_change,
            l.market_cap_usd
        FROM bounds b
        JOIN first_obs f ON f.coin_id = b.coin_id
        JOIN last_obs l ON l.coin_id = b.coin_id
        WHERE b.observation_count >= 2
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, (from_date, to_date))
        return cur.fetchall()
