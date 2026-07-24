from psycopg import Connection
from psycopg.rows import dict_row

"""CRUD access to app.paper_account / app.paper_transaction. No P&L or holdings-derivation logic
lives here — that belongs to paper_trading_service, which replays transactions in Python."""

_ACCOUNT_COLUMNS = "id, name, initial_cash, cash_balance, created_at, updated_at"
_TRANSACTION_COLUMNS = (
    "id, account_id, coin_symbol, transaction_type, quantity, execution_price, "
    "total_value, realized_profit, executed_at"
)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


def get_default_account(conn: Connection) -> dict | None:
    """The single paper-trading account this app supports (one default account is sufficient)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM app.paper_account ORDER BY id LIMIT 1")
        return cur.fetchone()


def create_account(conn: Connection, name: str, initial_cash) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            INSERT INTO app.paper_account (name, initial_cash, cash_balance)
            VALUES (%s, %s, %s)
            RETURNING {_ACCOUNT_COLUMNS}
            """,
            (name, initial_cash, initial_cash),
        )
        return cur.fetchone()


def lock_account(conn: Connection, account_id: int) -> dict | None:
    """SELECT ... FOR UPDATE: the concurrency guard for buy/sell. Must be called inside the same
    DB transaction as the trade's balance update + transaction insert (see paper_trading_service)
    so concurrent trades against the same account serialize instead of racing."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {_ACCOUNT_COLUMNS} FROM app.paper_account WHERE id = %s FOR UPDATE", (account_id,))
        return cur.fetchone()


def update_cash_balance(conn: Connection, account_id: int, new_balance) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE app.paper_account SET cash_balance = %s, updated_at = now() WHERE id = %s",
            (new_balance, account_id),
        )


def reset_account(conn: Connection, account_id: int) -> dict:
    """Wipe transaction history and restore cash_balance to initial_cash. Destructive to
    simulated data only; the caller (route) is expected to require explicit confirmation."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("DELETE FROM app.paper_transaction WHERE account_id = %s", (account_id,))
        cur.execute(
            f"""
            UPDATE app.paper_account
            SET cash_balance = initial_cash, updated_at = now()
            WHERE id = %s
            RETURNING {_ACCOUNT_COLUMNS}
            """,
            (account_id,),
        )
        return cur.fetchone()


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


def insert_transaction(
    conn: Connection,
    account_id: int,
    coin_symbol: str,
    transaction_type: str,
    quantity,
    execution_price,
    total_value,
    realized_profit,
) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            INSERT INTO app.paper_transaction
                (account_id, coin_symbol, transaction_type, quantity, execution_price, total_value, realized_profit)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING {_TRANSACTION_COLUMNS}
            """,
            (account_id, coin_symbol, transaction_type, quantity, execution_price, total_value, realized_profit),
        )
        return cur.fetchone()


def list_transactions(conn: Connection, account_id: int, limit: int | None) -> list[dict]:
    """Newest-first, for display."""
    sql = f"SELECT {_TRANSACTION_COLUMNS} FROM app.paper_transaction WHERE account_id = %s ORDER BY executed_at DESC, id DESC"
    params: list = [account_id]
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def list_transactions_chronological(conn: Connection, account_id: int) -> list[dict]:
    """Oldest-first, for replaying into current holdings / weighted-average cost."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT {_TRANSACTION_COLUMNS} FROM app.paper_transaction WHERE account_id = %s ORDER BY executed_at ASC, id ASC",
            (account_id,),
        )
        return cur.fetchall()
