from datetime import date, datetime

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
        SELECT coin_id, symbol, name, image_url, snapshot_date, price_usd, market_cap_usd,
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
        SELECT market_cap_position, coin_id, symbol, name, image_url, snapshot_date, market_cap_usd, price_usd
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
        SELECT volume_position, coin_id, symbol, name, image_url, snapshot_date, volume_24h_usd, price_usd
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


def fetch_current_market(conn: Connection, limit: int | None, order: str) -> dict | None:
    """Return the live current-market snapshot: an aggregate overview plus the per-coin list,
    both sourced from analytics.current_market_live (the most recently ingested staging run)
    rather than the daily-grain analytics.latest_snapshot. Used by the main dashboard's Take New
    Snapshot refresh so current values change on every press, even when the warehouse's
    (date_key, coin_key) idempotency guard means no new daily row landed. Returns None if nothing
    has been ingested yet."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT max(ingested_at) AS refreshed_at, count(*) AS coin_count,
                   sum(market_cap_usd) AS total_market_cap_usd, sum(volume_24h_usd) AS total_volume_24h_usd
            FROM analytics.current_market_live
            """
        )
        overview = cur.fetchone()

    if overview is None or overview["coin_count"] == 0:
        return None

    sql = f"""
        SELECT coin_id, symbol, name, image_url, price_usd, price_change_percentage_24h,
               market_cap_usd, volume_24h_usd, circulating_supply, market_cap_rank
        FROM analytics.current_market_live
        ORDER BY market_cap_usd {_direction(order)} NULLS LAST
    """
    params: list = []
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        coins = cur.fetchall()

    return {**overview, "coins": coins}


def fetch_prices_for_symbols(conn: Connection, symbols: list[str]) -> dict[str, dict]:
    """Return the latest snapshot row for each of the given symbols, keyed by uppercased symbol.

    Symbols with no current snapshot (never tracked, or since dropped out of the tracked set)
    are simply absent from the result. Daily-grain (analytics.latest_snapshot); prefer
    fetch_live_prices_for_symbols for anything that should reflect the most recent ingestion run.
    """
    if not symbols:
        return {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT coin_id, symbol, name, image_url, snapshot_date, price_usd, market_cap_usd,
                   volume_24h_usd, circulating_supply, market_cap_rank
            FROM analytics.latest_snapshot
            WHERE upper(symbol) = ANY(%s)
            """,
            ([s.upper() for s in symbols],),
        )
        return {row["symbol"].upper(): row for row in cur.fetchall()}


def fetch_live_prices_for_symbols(conn: Connection, symbols: list[str]) -> dict[str, dict]:
    """Live counterpart to fetch_prices_for_symbols: prices each of the given symbols from
    analytics.current_market_live (the most recently ingested staging run) instead of the
    daily-grain analytics.latest_snapshot. Used by portfolio/paper-trading valuation and trade
    execution so the price shown in the Buy/Sell picker always matches what's charged/credited.
    Symbols with no current live row are simply absent from the result.
    """
    if not symbols:
        return {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT coin_id, symbol, name, image_url, price_usd, price_change_percentage_24h,
                   market_cap_usd, volume_24h_usd, circulating_supply, market_cap_rank
            FROM analytics.current_market_live
            WHERE upper(symbol) = ANY(%s)
            """,
            ([s.upper() for s in symbols],),
        )
        return {row["symbol"].upper(): row for row in cur.fetchall()}


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
        SELECT coin_id, symbol, name, image_url, snapshot_date, price_usd, market_cap_usd,
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


def fetch_history_summary(
    conn: Connection,
    coin_symbol: str,
    from_date: date | None,
    to_date: date | None,
) -> dict | None:
    """Return period summary statistics for one coin's history, optionally bounded by date range:
    start/end price, absolute/percent change, min/max/avg price, observation count, and the
    first/last snapshot dates in the period. Computed in SQL so the frontend never has to
    recompute the same aggregates from a raw row list. Returns None if the symbol has no rows in
    the requested range (distinct from `fetch_history`'s empty list, since a summary is scalar)."""
    sql = (
        """
        WITH filtered AS (
            SELECT coin_id, symbol, name, snapshot_date, price_usd
            FROM analytics.market_history
            WHERE lower(symbol) = lower(%s)
        """
        + (" AND snapshot_date >= %s" if from_date is not None else "")
        + (" AND snapshot_date <= %s" if to_date is not None else "")
        + """
        ),
        bounds AS (
            SELECT
                (SELECT coin_id FROM filtered LIMIT 1) AS coin_id,
                (SELECT symbol FROM filtered LIMIT 1) AS symbol,
                (SELECT name FROM filtered LIMIT 1) AS name,
                MIN(snapshot_date) AS period_start_date,
                MAX(snapshot_date) AS period_end_date,
                MIN(price_usd) AS min_price,
                MAX(price_usd) AS max_price,
                AVG(price_usd) AS avg_price,
                COUNT(*) AS observation_count
            FROM filtered
        )
        SELECT
            b.coin_id, b.symbol, b.name,
            b.period_start_date, b.period_end_date,
            fs.price_usd AS period_start_price,
            fe.price_usd AS period_end_price,
            (fe.price_usd - fs.price_usd) AS absolute_change,
            CASE WHEN fs.price_usd = 0 THEN NULL
                 ELSE (fe.price_usd - fs.price_usd) / fs.price_usd * 100 END AS percent_change,
            b.min_price, b.max_price, b.avg_price, b.observation_count
        FROM bounds b
        JOIN filtered fs ON fs.snapshot_date = b.period_start_date
        JOIN filtered fe ON fe.snapshot_date = b.period_end_date
        LIMIT 1
        """
    )
    params: list = [coin_symbol]
    if from_date is not None:
        params.append(from_date)
    if to_date is not None:
        params.append(to_date)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def symbol_has_intraday(conn: Connection, coin_symbol: str) -> bool:
    """Check whether coin_symbol appears anywhere in the analytics intraday view. Kept separate
    from symbol_has_history since a coin can be a known daily-tracked coin with zero intraday
    observations (never ingested via etl/ingest_intraday_market_data.py) -- that's a valid 'known
    coin, no intraday data' state, distinct from an unknown coin (404)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM dw.dim_coin WHERE lower(symbol) = lower(%s) LIMIT 1",
            (coin_symbol,),
        )
        return cur.fetchone() is not None


def fetch_intraday(
    conn: Connection,
    coin_symbol: str,
    from_timestamp: datetime | None,
    to_timestamp: datetime | None,
    order: str,
    limit: int | None,
) -> list[dict]:
    """Return intraday (sub-daily) observations for one coin, optionally bounded by timestamp
    range. Backed by analytics.market_intraday (dw.fact_market_intraday), entirely separate from
    fetch_history's daily-grain query."""
    sql = """
        SELECT coin_id, symbol, name, image_url, observation_timestamp, price_usd, market_cap_usd, volume_24h_usd
        FROM analytics.market_intraday
        WHERE lower(symbol) = lower(%s)
    """
    params: list = [coin_symbol]
    if from_timestamp is not None:
        sql += " AND observation_timestamp >= %s"
        params.append(from_timestamp)
    if to_timestamp is not None:
        sql += " AND observation_timestamp <= %s"
        params.append(to_timestamp)
    sql += f" ORDER BY observation_timestamp {_direction(order)}"
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


_MOVER_FIELDS = """
        b.coin_id, b.symbol, b.name, b.image_url, b.observation_count,
        f.start_price, l.end_price, b.high_price, b.low_price,
        l.volume_24h_usd, l.market_cap_usd, {rank_expr} AS market_cap_rank,
        CASE WHEN f.start_price = 0 THEN NULL
             ELSE (l.end_price - f.start_price) / f.start_price * 100 END AS percent_change,
        CASE WHEN b.low_price = 0 THEN NULL
             ELSE (b.high_price - b.low_price) / b.low_price * 100 END AS volatility_percent
"""


def fetch_daily_movers(conn: Connection, from_date: date, to_date: date | None) -> list[dict]:
    """Return per-coin price movement over a daily-grain date range, computed strictly from
    real observations already loaded into analytics.market_history: the first and last snapshot
    inside [from_date, to_date], plus the period high/low for a volatility figure. Coins with
    fewer than 2 observations in range are excluded -- a change can't be computed (and must never
    be estimated) from a single point. Powers the Market Leaders dashboard's 7d/30d/90d/1y periods."""
    sql = """
        WITH filtered AS (
            SELECT coin_id, symbol, name, image_url, snapshot_date, price_usd, volume_24h_usd, market_cap_usd, market_cap_rank
            FROM analytics.market_history
            WHERE snapshot_date >= %s
    """
    params: list = [from_date]
    if to_date is not None:
        sql += " AND snapshot_date <= %s"
        params.append(to_date)
    sql += (
        """
        ),
        bounds AS (
            SELECT coin_id, symbol, name, image_url,
                   MIN(price_usd) AS low_price,
                   MAX(price_usd) AS high_price,
                   COUNT(*) AS observation_count
            FROM filtered
            GROUP BY coin_id, symbol, name, image_url
        ),
        first_obs AS (
            SELECT DISTINCT ON (coin_id) coin_id, price_usd AS start_price
            FROM filtered ORDER BY coin_id, snapshot_date ASC
        ),
        last_obs AS (
            SELECT DISTINCT ON (coin_id) coin_id, price_usd AS end_price, volume_24h_usd, market_cap_usd, market_cap_rank
            FROM filtered ORDER BY coin_id, snapshot_date DESC
        )
        SELECT """
        + _MOVER_FIELDS.format(rank_expr="l.market_cap_rank")
        + """
        FROM bounds b
        JOIN first_obs f ON f.coin_id = b.coin_id
        JOIN last_obs l ON l.coin_id = b.coin_id
        WHERE b.observation_count >= 2
        """
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_daily_observation_range(conn: Connection, from_date: date, to_date: date | None) -> tuple[date | None, date | None]:
    """Return (earliest, latest) snapshot_date actually loaded in analytics.market_history within
    [from_date, to_date], regardless of the >=2-observation qualification fetch_daily_movers
    applies. Lets the Market Leaders dashboard tell 'no coins qualified' apart from 'no history
    has been loaded for this range at all' even when the mover list comes back empty."""
    sql = "SELECT min(snapshot_date), max(snapshot_date) FROM analytics.market_history WHERE snapshot_date >= %s"
    params: list = [from_date]
    if to_date is not None:
        sql += " AND snapshot_date <= %s"
        params.append(to_date)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return (row[0], row[1]) if row else (None, None)


def fetch_intraday_observation_range(
    conn: Connection, from_ts: datetime, to_ts: datetime | None
) -> tuple[datetime | None, datetime | None]:
    """Intraday counterpart to fetch_daily_observation_range, backed by analytics.market_intraday."""
    sql = (
        "SELECT min(observation_timestamp), max(observation_timestamp) "
        "FROM analytics.market_intraday WHERE observation_timestamp >= %s"
    )
    params: list = [from_ts]
    if to_ts is not None:
        sql += " AND observation_timestamp <= %s"
        params.append(to_ts)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return (row[0], row[1]) if row else (None, None)


def fetch_intraday_movers(conn: Connection, from_ts: datetime, to_ts: datetime | None) -> list[dict]:
    """Return per-coin price movement over a sub-daily timestamp range, computed strictly from
    real observations already loaded into analytics.market_intraday (see fetch_daily_movers for
    the shared exclusion/never-estimate rules). Intraday rows carry no market_cap_rank of their
    own, so it's left-joined in from analytics.latest_snapshot for display purposes only --
    it plays no part in the percent_change/volatility math. Powers the Market Leaders dashboard's
    "Today" period."""
    sql = """
        WITH filtered AS (
            SELECT coin_id, symbol, name, image_url, observation_timestamp, price_usd, volume_24h_usd, market_cap_usd
            FROM analytics.market_intraday
            WHERE observation_timestamp >= %s
    """
    params: list = [from_ts]
    if to_ts is not None:
        sql += " AND observation_timestamp <= %s"
        params.append(to_ts)
    sql += (
        """
        ),
        bounds AS (
            SELECT coin_id, symbol, name, image_url,
                   MIN(price_usd) AS low_price,
                   MAX(price_usd) AS high_price,
                   COUNT(*) AS observation_count
            FROM filtered
            GROUP BY coin_id, symbol, name, image_url
        ),
        first_obs AS (
            SELECT DISTINCT ON (coin_id) coin_id, price_usd AS start_price
            FROM filtered ORDER BY coin_id, observation_timestamp ASC
        ),
        last_obs AS (
            SELECT DISTINCT ON (coin_id) coin_id, price_usd AS end_price, volume_24h_usd, market_cap_usd
            FROM filtered ORDER BY coin_id, observation_timestamp DESC
        )
        SELECT """
        + _MOVER_FIELDS.format(rank_expr="ls.market_cap_rank")
        + """
        FROM bounds b
        JOIN first_obs f ON f.coin_id = b.coin_id
        JOIN last_obs l ON l.coin_id = b.coin_id
        LEFT JOIN analytics.latest_snapshot ls ON ls.coin_id = b.coin_id
        WHERE b.observation_count >= 2
        """
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_coin_count(conn: Connection) -> int:
    """Total number of currently-tracked coins, for the Market Leaders summary bar."""
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM analytics.latest_snapshot")
        return cur.fetchone()[0]


def fetch_latest_update_at(conn: Connection) -> datetime | None:
    """Timestamp the warehouse was last successfully loaded (audit.etl_run), for the Market
    Leaders summary bar. None if the warehouse-load pipeline has never succeeded."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT max(finished_at) FROM audit.etl_run
            WHERE pipeline_name = 'coingecko_warehouse_load' AND status = 'succeeded'
            """
        )
        return cur.fetchone()[0]


def fetch_intraday_count_today(conn: Connection) -> int:
    """Number of dw.fact_market_intraday rows observed today (current UTC calendar date). Part
    12's optional 'Intraday snapshots today: N' status line on the manual snapshot button."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM dw.fact_market_intraday
            WHERE observation_timestamp >= date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
            """
        )
        return cur.fetchone()[0]


def fetch_intraday_today(conn: Connection, coin_symbol: str) -> list[dict]:
    """Return today's (current UTC calendar date) intraday observations for one coin, sorted
    chronologically for charting. A thin, focused convenience over fetch_intraday: the frontend's
    'Today' range always wants exactly this and nothing else."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT coin_id, symbol, name, image_url, observation_timestamp, price_usd, market_cap_usd, volume_24h_usd
            FROM analytics.market_intraday
            WHERE lower(symbol) = lower(%s)
              AND observation_timestamp >= date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
            ORDER BY observation_timestamp ASC
            """,
            (coin_symbol,),
        )
        return cur.fetchall()
