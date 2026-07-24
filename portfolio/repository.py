from psycopg import Connection
from psycopg.rows import dict_row

"""CRUD access to app.portfolio / app.portfolio_holding. No valuation logic lives here —
that belongs to portfolio_service, which combines these rows with warehouse prices."""


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


def create_portfolio(conn: Connection, name: str, description: str | None) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO app.portfolio (name, description)
            VALUES (%s, %s)
            RETURNING id, name, description, created_at, updated_at
            """,
            (name, description),
        )
        return cur.fetchone()


def list_portfolios(conn: Connection) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, name, description, created_at, updated_at FROM app.portfolio ORDER BY created_at"
        )
        return cur.fetchall()


def get_portfolio(conn: Connection, portfolio_id: int) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, name, description, created_at, updated_at FROM app.portfolio WHERE id = %s",
            (portfolio_id,),
        )
        return cur.fetchone()


def update_portfolio(conn: Connection, portfolio_id: int, name: str, description: str | None) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            UPDATE app.portfolio
            SET name = %s, description = %s, updated_at = now()
            WHERE id = %s
            RETURNING id, name, description, created_at, updated_at
            """,
            (name, description, portfolio_id),
        )
        return cur.fetchone()


def delete_portfolio(conn: Connection, portfolio_id: int) -> bool:
    """Delete a portfolio. Holdings are removed by the ON DELETE CASCADE foreign key."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM app.portfolio WHERE id = %s", (portfolio_id,))
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Portfolio holdings
# ---------------------------------------------------------------------------

_HOLDING_COLUMNS = "id, portfolio_id, coin_symbol, quantity, average_buy_price, created_at, updated_at"


def create_holding(
    conn: Connection, portfolio_id: int, coin_symbol: str, quantity: float, average_buy_price: float
) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            INSERT INTO app.portfolio_holding (portfolio_id, coin_symbol, quantity, average_buy_price)
            VALUES (%s, %s, %s, %s)
            RETURNING {_HOLDING_COLUMNS}
            """,
            (portfolio_id, coin_symbol, quantity, average_buy_price),
        )
        return cur.fetchone()


def list_holdings(conn: Connection, portfolio_id: int) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT {_HOLDING_COLUMNS} FROM app.portfolio_holding WHERE portfolio_id = %s ORDER BY created_at",
            (portfolio_id,),
        )
        return cur.fetchall()


def list_holdings_for_portfolios(conn: Connection, portfolio_ids: list[int]) -> dict[int, list[dict]]:
    """Batched form of list_holdings for many portfolios in one query, grouped by portfolio_id.
    Used by portfolio_service.list_portfolios so a page of N portfolios costs one holdings query
    total instead of N (which also lets the caller price every holding across every portfolio with
    a single warehouse lookup instead of N)."""
    if not portfolio_ids:
        return {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT {_HOLDING_COLUMNS} FROM app.portfolio_holding
            WHERE portfolio_id = ANY(%s)
            ORDER BY portfolio_id, created_at
            """,
            (portfolio_ids,),
        )
        rows = cur.fetchall()

    grouped: dict[int, list[dict]] = {portfolio_id: [] for portfolio_id in portfolio_ids}
    for row in rows:
        grouped[row["portfolio_id"]].append(row)
    return grouped


def get_holding(conn: Connection, holding_id: int) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT {_HOLDING_COLUMNS} FROM app.portfolio_holding WHERE id = %s",
            (holding_id,),
        )
        return cur.fetchone()


def holding_exists_for_symbol(conn: Connection, portfolio_id: int, coin_symbol: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM app.portfolio_holding WHERE portfolio_id = %s AND coin_symbol = %s",
            (portfolio_id, coin_symbol),
        )
        return cur.fetchone() is not None


def update_holding(conn: Connection, holding_id: int, quantity: float, average_buy_price: float) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            UPDATE app.portfolio_holding
            SET quantity = %s, average_buy_price = %s, updated_at = now()
            WHERE id = %s
            RETURNING {_HOLDING_COLUMNS}
            """,
            (quantity, average_buy_price, holding_id),
        )
        return cur.fetchone()


def delete_holding(conn: Connection, holding_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM app.portfolio_holding WHERE id = %s", (holding_id,))
        return cur.rowcount > 0
