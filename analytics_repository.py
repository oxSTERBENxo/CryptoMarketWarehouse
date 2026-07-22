from datetime import date

from psycopg import Connection
from psycopg.rows import dict_row

_DIRECTIONS = {"asc": "ASC", "desc": "DESC"}


def _direction(order: str) -> str:
    try:
        return _DIRECTIONS[order]
    except KeyError:
        raise ValueError(f"Unsupported sort order: {order!r}") from None


def fetch_overview(conn: Connection) -> dict | None:
    """Return the single-row current market overview, or None if no snapshot has been loaded yet."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT snapshot_date, coin_count, total_market_cap_usd, total_volume_24h_usd
            FROM analytics.current_market_overview
            """
        )
        return cur.fetchone()


def fetch_latest(conn: Connection, limit: int | None, order: str) -> list[dict]:
    """Return the latest snapshot for every coin, sorted by market cap."""
    sql = f"""
        SELECT coin_id, symbol, name, snapshot_date, price_usd, market_cap_usd,
               volume_24h_usd, circulating_supply, market_cap_rank
        FROM analytics.latest_snapshot
        ORDER BY market_cap_usd {_direction(order)} NULLS LAST
    """
    params: list = []
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_top_market_cap(conn: Connection, limit: int | None, order: str) -> list[dict]:
    """Return coins ranked by market cap."""
    sql = f"""
        SELECT market_cap_position, coin_id, symbol, name, snapshot_date, market_cap_usd, price_usd
        FROM analytics.top_market_cap
        ORDER BY market_cap_usd {_direction(order)} NULLS LAST
    """
    params: list = []
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_top_volume(conn: Connection, limit: int | None, order: str) -> list[dict]:
    """Return coins ranked by 24h volume."""
    sql = f"""
        SELECT volume_position, coin_id, symbol, name, snapshot_date, volume_24h_usd, price_usd
        FROM analytics.top_volume
        ORDER BY volume_24h_usd {_direction(order)} NULLS LAST
    """
    params: list = []
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def symbol_has_history(conn: Connection, coin_symbol: str) -> bool:
    """Check whether coin_symbol appears anywhere in the analytics history view."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM analytics.market_history WHERE lower(symbol) = lower(%s) LIMIT 1",
            (coin_symbol,),
        )
        return cur.fetchone() is not None


def fetch_history(
    conn: Connection,
    coin_symbol: str,
    from_date: date | None,
    to_date: date | None,
    order: str,
    limit: int | None,
) -> list[dict]:
    """Return the historical time series for one coin, optionally bounded by date range."""
    sql = """
        SELECT coin_id, symbol, name, snapshot_date, price_usd, market_cap_usd,
               volume_24h_usd, circulating_supply, market_cap_rank
        FROM analytics.market_history
        WHERE lower(symbol) = lower(%s)
    """
    params: list = [coin_symbol]
    if from_date is not None:
        sql += " AND snapshot_date >= %s"
        params.append(from_date)
    if to_date is not None:
        sql += " AND snapshot_date <= %s"
        params.append(to_date)
    sql += f" ORDER BY snapshot_date {_direction(order)}"
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()
