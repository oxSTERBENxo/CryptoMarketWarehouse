import os
from decimal import ROUND_HALF_UP, Decimal

from psycopg import Connection

from analytics import repository as analytics_repository
from utils import metrics
from paper_trading import repository as repo

"""Paper-trading business logic: account bootstrap, atomic buy/sell execution, and valuation.

Holdings and weighted-average cost are never stored — they're derived by replaying a symbol's
BUY/SELL rows in `executed_at` order (`_replay_holdings`). This is what keeps
`app.paper_transaction` an honest, immutable audit trail: a later trade can never rewrite an
earlier transaction's stored price, and "current holdings" is always just a pure function of
history.

Weighted-average-cost method (the realized-P&L calculation this module implements):
  - BUY qty q @ price p:  avg_cost' = (qty*avg_cost + q*p) / (qty+q);  qty' = qty + q.
  - SELL qty q:            realized_profit = (execution_price - avg_cost) * q, computed once and
                            stored on that transaction row; qty' = qty - q; avg_cost is
                            unchanged — weighted-average cost basis only moves on buys.
  - An account's total realized profit is the sum of every SELL row's stored realized_profit.

Execution price always comes from `analytics_repository.fetch_live_prices_for_symbols` (the
warehouse's live current-market view, matching what the Buy/Sell picker displays) — this module
never calls CoinGecko directly.

Concurrency/atomicity: `buy`/`sell` lock the account row (`SELECT ... FOR UPDATE`, via
`repo.lock_account`) before validating and writing, inside the one DB transaction the FastAPI
request's connection dependency already manages (commit on clean return, rollback on exception —
see `paper_trading_routes._get_db`). Concurrent trade requests against the same account therefore
serialize rather than race: cash and holdings can never go negative under concurrency, and any
failure between the lock and the final write rolls back the balance update together with the
transaction insert. This serialization is why no 409 is raised for concurrent trades — the lock
prevents the conflict from ever being observable, rather than detecting it after the fact.
"""

_CENTS = Decimal("0.01")

DEFAULT_ACCOUNT_NAME = "Paper Trading Account"
DEFAULT_INITIAL_CASH = Decimal(os.environ.get("PAPER_TRADING_INITIAL_CASH", "100000.00"))


class UnknownCoinSymbolError(Exception):
    def __init__(self, coin_symbol: str) -> None:
        super().__init__(f"Unknown coin symbol: {coin_symbol!r}. It has no snapshot in the current warehouse data.")
        self.coin_symbol = coin_symbol


class InsufficientCashError(Exception):
    def __init__(self, coin_symbol: str, required: Decimal, available: Decimal) -> None:
        super().__init__(
            f"Insufficient cash to buy {coin_symbol}: requires {required}, {available} available"
        )
        self.coin_symbol = coin_symbol
        self.required = required
        self.available = available


class InsufficientHoldingsError(Exception):
    def __init__(self, coin_symbol: str, requested: Decimal, held: Decimal) -> None:
        super().__init__(
            f"Insufficient holdings to sell {coin_symbol}: requested {requested}, {held} held"
        )
        self.coin_symbol = coin_symbol
        self.requested = requested
        self.held = held


def _round_cents(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _replay_holdings(transactions: list[dict]) -> dict[str, dict]:
    """Replay a chronologically-ordered transaction list into current per-symbol holdings
    (quantity, weighted-average cost), per the method documented on this module. Symbols fully
    sold off (quantity <= 0) are dropped — they're not "held" anymore."""
    holdings: dict[str, dict] = {}
    for tx in transactions:
        symbol = tx["coin_symbol"]
        state = holdings.setdefault(symbol, {"quantity": Decimal(0), "avg_cost": Decimal(0)})
        qty = Decimal(tx["quantity"])
        price = Decimal(tx["execution_price"])

        if tx["transaction_type"] == "BUY":
            new_qty = state["quantity"] + qty
            state["avg_cost"] = (state["quantity"] * state["avg_cost"] + qty * price) / new_qty
            state["quantity"] = new_qty
        else:  # SELL
            state["quantity"] -= qty

    return {symbol: state for symbol, state in holdings.items() if state["quantity"] > 0}


def _current_holding(conn: Connection, account_id: int, coin_symbol: str) -> dict:
    transactions = repo.list_transactions_chronological(conn, account_id)
    return _replay_holdings(transactions).get(coin_symbol, {"quantity": Decimal(0), "avg_cost": Decimal(0)})


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


def get_or_create_account(conn: Connection) -> dict:
    """One default account is sufficient for now: created lazily on first access."""
    account = repo.get_default_account(conn)
    if account is not None:
        return account
    return repo.create_account(conn, DEFAULT_ACCOUNT_NAME, DEFAULT_INITIAL_CASH)


def reset_account(conn: Connection) -> dict:
    account = get_or_create_account(conn)
    return repo.reset_account(conn, account["id"])


# ---------------------------------------------------------------------------
# Trading
# ---------------------------------------------------------------------------


def buy(conn: Connection, coin_symbol: str, quantity: Decimal) -> dict:
    coin_symbol = coin_symbol.upper()
    account = get_or_create_account(conn)

    prices = analytics_repository.fetch_live_prices_for_symbols(conn, [coin_symbol])
    snapshot = prices.get(coin_symbol)
    if snapshot is None:
        raise UnknownCoinSymbolError(coin_symbol)
    execution_price = Decimal(str(snapshot["price_usd"]))
    total_value = _round_cents(quantity * execution_price)

    locked = repo.lock_account(conn, account["id"])
    cash_balance = Decimal(locked["cash_balance"])
    if total_value > cash_balance:
        raise InsufficientCashError(coin_symbol, total_value, cash_balance)

    repo.update_cash_balance(conn, account["id"], cash_balance - total_value)
    return repo.insert_transaction(conn, account["id"], coin_symbol, "BUY", quantity, execution_price, total_value, None)


def sell(conn: Connection, coin_symbol: str, quantity: Decimal) -> dict:
    coin_symbol = coin_symbol.upper()
    account = get_or_create_account(conn)

    prices = analytics_repository.fetch_live_prices_for_symbols(conn, [coin_symbol])
    snapshot = prices.get(coin_symbol)
    if snapshot is None:
        raise UnknownCoinSymbolError(coin_symbol)
    execution_price = Decimal(str(snapshot["price_usd"]))

    locked = repo.lock_account(conn, account["id"])
    holding = _current_holding(conn, account["id"], coin_symbol)
    if quantity > holding["quantity"]:
        raise InsufficientHoldingsError(coin_symbol, quantity, holding["quantity"])

    realized_profit = _round_cents((execution_price - holding["avg_cost"]) * quantity)
    total_value = _round_cents(quantity * execution_price)
    cash_balance = Decimal(locked["cash_balance"])

    repo.update_cash_balance(conn, account["id"], cash_balance + total_value)
    return repo.insert_transaction(
        conn, account["id"], coin_symbol, "SELL", quantity, execution_price, total_value, realized_profit
    )


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------


def list_transactions(conn: Connection, limit: int | None = None) -> list[dict]:
    account = get_or_create_account(conn)
    return repo.list_transactions(conn, account["id"], limit)


def get_portfolio(conn: Connection) -> dict:
    account = get_or_create_account(conn)
    transactions = repo.list_transactions_chronological(conn, account["id"])
    holdings_state = _replay_holdings(transactions)

    realized_profit = sum(
        (Decimal(tx["realized_profit"]) for tx in transactions if tx["transaction_type"] == "SELL" and tx["realized_profit"] is not None),
        Decimal(0),
    )

    prices = analytics_repository.fetch_live_prices_for_symbols(conn, list(holdings_state.keys()))

    priced_holdings = []
    for symbol, state in holdings_state.items():
        snapshot = prices.get(symbol)
        quantity = state["quantity"]
        avg_cost = state["avg_cost"]
        cost_basis = quantity * avg_cost

        current_price = Decimal(str(snapshot["price_usd"])) if snapshot else None
        current_value = quantity * current_price if current_price is not None else None
        unrealized_profit = current_value - cost_basis if current_value is not None else None
        unrealized_percent = metrics.safe_percent(unrealized_profit, cost_basis)

        priced_holdings.append(
            {
                "coin_symbol": symbol,
                "coin_name": snapshot["name"] if snapshot else None,
                "image_url": snapshot["image_url"] if snapshot else None,
                "price_change_percentage_24h": snapshot["price_change_percentage_24h"] if snapshot else None,
                "quantity": quantity,
                "average_cost": avg_cost,
                "current_price": current_price,
                "current_value": current_value,
                "cost_basis": cost_basis,
                "unrealized_profit": unrealized_profit,
                "unrealized_percent": unrealized_percent,
            }
        )

    holdings_value = sum((h["current_value"] for h in priced_holdings if h["current_value"] is not None), Decimal(0))
    invested_value = sum((h["cost_basis"] for h in priced_holdings), Decimal(0))
    unrealized_total = sum((h["unrealized_profit"] for h in priced_holdings if h["unrealized_profit"] is not None), Decimal(0))

    cash_balance = Decimal(account["cash_balance"])
    total_equity = cash_balance + holdings_value
    initial_cash = Decimal(account["initial_cash"])
    total_return_percent = metrics.safe_percent(total_equity - initial_cash, initial_cash)

    for holding in priced_holdings:
        allocation_percent = metrics.safe_percent(holding["current_value"], total_equity)
        holding["allocation_percent"] = float(allocation_percent) if allocation_percent is not None else None

    priced_with_percent = [h for h in priced_holdings if h["unrealized_percent"] is not None]
    best_performer = max(priced_with_percent, key=lambda h: h["unrealized_percent"])["coin_symbol"] if priced_with_percent else None
    worst_performer = min(priced_with_percent, key=lambda h: h["unrealized_percent"])["coin_symbol"] if priced_with_percent else None

    return {
        "account": account,
        "holdings": priced_holdings,
        "cash_balance": cash_balance,
        "invested_value": invested_value,
        "holdings_value": holdings_value,
        "total_equity": total_equity,
        "realized_profit": realized_profit,
        "unrealized_profit": unrealized_total,
        "total_return_percent": total_return_percent,
        "best_performer": best_performer,
        "worst_performer": worst_performer,
    }
