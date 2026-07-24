from psycopg import Connection
from psycopg.errors import UniqueViolation

from analytics import repository as analytics_repository
from utils import metrics
from portfolio import repository as repo

"""Portfolio business logic: CRUD orchestration plus valuation.

Valuation always prices holdings from the warehouse's live current-market view
(`analytics.current_market_live`, via analytics_repository.fetch_live_prices_for_symbols) — never
from CoinGecko directly, and never stored. This matches the price/24h-change the Manual Holdings
coin picker displays when adding a holding. A holding's price is unavailable only if its coin has
since dropped out of the tracked set entirely; that holding is then excluded from the
value/profit totals (its cost basis is still shown on the row) so the portfolio summary stays
internally consistent.
"""


class PortfolioNotFoundError(Exception):
    def __init__(self, portfolio_id: int) -> None:
        super().__init__(f"Portfolio {portfolio_id} not found")
        self.portfolio_id = portfolio_id


class HoldingNotFoundError(Exception):
    def __init__(self, holding_id: int) -> None:
        super().__init__(f"Holding {holding_id} not found")
        self.holding_id = holding_id


class UnknownCoinSymbolError(Exception):
    def __init__(self, coin_symbol: str) -> None:
        super().__init__(f"Unknown coin symbol: {coin_symbol!r}. It has no snapshot in the current warehouse data.")
        self.coin_symbol = coin_symbol


class DuplicateHoldingError(Exception):
    def __init__(self, portfolio_id: int, coin_symbol: str) -> None:
        super().__init__(f"Portfolio {portfolio_id} already has a holding for {coin_symbol!r}")
        self.portfolio_id = portfolio_id
        self.coin_symbol = coin_symbol


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------


def _price_holdings(conn: Connection, holding_rows: list[dict], prices: dict[str, dict] | None = None) -> list[dict]:
    """Attach warehouse pricing/valuation fields to each raw holding row.

    `prices` lets a caller that already priced a batch of symbols (e.g. list_portfolios pricing
    every holding across every portfolio in one warehouse lookup) reuse that lookup instead of
    this function issuing its own; single-holding-list callers omit it and it's fetched here.
    """
    if prices is None:
        symbols = [row["coin_symbol"] for row in holding_rows]
        prices = analytics_repository.fetch_live_prices_for_symbols(conn, symbols)

    priced: list[dict] = []
    for row in holding_rows:
        snapshot = prices.get(row["coin_symbol"].upper())
        quantity = float(row["quantity"])
        average_buy_price = float(row["average_buy_price"])
        cost_basis = quantity * average_buy_price

        current_price = float(snapshot["price_usd"]) if snapshot else None
        current_value = quantity * current_price if current_price is not None else None
        unrealized_profit = current_value - cost_basis if current_value is not None else None
        profit_percent = metrics.safe_percent(unrealized_profit, cost_basis)

        priced.append(
            {
                "id": row["id"],
                "portfolio_id": row["portfolio_id"],
                "coin_symbol": row["coin_symbol"],
                "coin_name": snapshot["name"] if snapshot else None,
                "image_url": snapshot["image_url"] if snapshot else None,
                "price_change_percentage_24h": snapshot["price_change_percentage_24h"] if snapshot else None,
                "quantity": quantity,
                "average_buy_price": average_buy_price,
                "current_price": current_price,
                "current_value": current_value,
                "cost_basis": cost_basis,
                "unrealized_profit": unrealized_profit,
                "profit_percent": profit_percent,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return priced


def _summarize(priced_holdings: list[dict]) -> dict:
    """Aggregate totals over holdings that could be priced, so value and cost basis line up."""
    valued = [h for h in priced_holdings if h["current_value"] is not None]
    total_value = sum(h["current_value"] for h in valued)
    total_cost_basis = sum(h["cost_basis"] for h in valued)
    total_unrealized_profit = total_value - total_cost_basis
    total_unrealized_percent = metrics.safe_percent(total_unrealized_profit, total_cost_basis)

    return {
        "total_value": total_value,
        "total_cost_basis": total_cost_basis,
        "total_unrealized_profit": total_unrealized_profit,
        "total_unrealized_percent": total_unrealized_percent,
    }


def _detail(conn: Connection, portfolio: dict) -> dict:
    holdings = _price_holdings(conn, repo.list_holdings(conn, portfolio["id"]))
    return {**portfolio, "holdings": holdings, "summary": _summarize(holdings)}


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


def create_portfolio(conn: Connection, name: str, description: str | None) -> dict:
    portfolio = repo.create_portfolio(conn, name, description)
    return _detail(conn, portfolio)


def list_portfolios(conn: Connection) -> list[dict]:
    """Batched to avoid an N+1: previously issued 1 + 2*N queries (holdings + prices per
    portfolio) for N portfolios; now issues exactly 3 total regardless of N."""
    portfolios = repo.list_portfolios(conn)
    holdings_by_portfolio = repo.list_holdings_for_portfolios(conn, [p["id"] for p in portfolios])

    all_symbols = [row["coin_symbol"] for rows in holdings_by_portfolio.values() for row in rows]
    prices = analytics_repository.fetch_live_prices_for_symbols(conn, all_symbols)

    details = []
    for portfolio in portfolios:
        holdings = _price_holdings(conn, holdings_by_portfolio.get(portfolio["id"], []), prices=prices)
        details.append({**portfolio, "holdings": holdings, "summary": _summarize(holdings)})
    return details


def get_portfolio(conn: Connection, portfolio_id: int) -> dict:
    portfolio = repo.get_portfolio(conn, portfolio_id)
    if portfolio is None:
        raise PortfolioNotFoundError(portfolio_id)
    return _detail(conn, portfolio)


def rename_portfolio(conn: Connection, portfolio_id: int, name: str, description: str | None) -> dict:
    portfolio = repo.update_portfolio(conn, portfolio_id, name, description)
    if portfolio is None:
        raise PortfolioNotFoundError(portfolio_id)
    return _detail(conn, portfolio)


def delete_portfolio(conn: Connection, portfolio_id: int) -> None:
    if not repo.delete_portfolio(conn, portfolio_id):
        raise PortfolioNotFoundError(portfolio_id)


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------


def add_holding(conn: Connection, portfolio_id: int, coin_symbol: str, quantity: float, average_buy_price: float) -> dict:
    if repo.get_portfolio(conn, portfolio_id) is None:
        raise PortfolioNotFoundError(portfolio_id)

    prices = analytics_repository.fetch_live_prices_for_symbols(conn, [coin_symbol])
    if coin_symbol.upper() not in prices:
        raise UnknownCoinSymbolError(coin_symbol)

    if repo.holding_exists_for_symbol(conn, portfolio_id, coin_symbol):
        raise DuplicateHoldingError(portfolio_id, coin_symbol)

    # The check above is TOCTOU-racy under concurrent requests for the same coin; the unique
    # constraint on (portfolio_id, coin_symbol) is the real guard, so translate a violation of
    # it into the same DuplicateHoldingError rather than letting it surface as a 500.
    try:
        holding = repo.create_holding(conn, portfolio_id, coin_symbol, quantity, average_buy_price)
    except UniqueViolation as exc:
        raise DuplicateHoldingError(portfolio_id, coin_symbol) from exc
    return _price_holdings(conn, [holding])[0]


def edit_holding(conn: Connection, holding_id: int, quantity: float, average_buy_price: float) -> dict:
    holding = repo.update_holding(conn, holding_id, quantity, average_buy_price)
    if holding is None:
        raise HoldingNotFoundError(holding_id)
    return _price_holdings(conn, [holding])[0]


def remove_holding(conn: Connection, holding_id: int) -> None:
    if not repo.delete_holding(conn, holding_id):
        raise HoldingNotFoundError(holding_id)
