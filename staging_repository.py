from psycopg import Connection

from coingecko import CoinMarketData

INSERT_SQL = """
    INSERT INTO staging.coingecko_market_snapshot
        (run_id, coin_id, symbol, name, current_price, market_cap, market_cap_rank, total_volume, circulating_supply)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def insert_market_snapshots(conn: Connection, run_id: int, coins: list[CoinMarketData]) -> int:
    """Insert one staging row per coin for the given run. Returns the number of rows inserted."""
    rows = [
        (
            run_id,
            coin.id,
            coin.symbol,
            coin.name,
            coin.current_price,
            coin.market_cap,
            coin.market_cap_rank,
            coin.total_volume,
            coin.circulating_supply,
        )
        for coin in coins
    ]
    with conn.cursor() as cur:
        cur.executemany(INSERT_SQL, rows)
    return len(rows)
