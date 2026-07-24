from datetime import datetime, timezone
from decimal import Decimal

import pytest

from paper_trading import service

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _account(**overrides) -> dict:
    account = {
        "id": 1,
        "name": "Paper Trading Account",
        "initial_cash": Decimal("100000.00"),
        "cash_balance": Decimal("100000.00"),
        "created_at": NOW,
        "updated_at": NOW,
    }
    account.update(overrides)
    return account


def _snapshot(symbol: str, price: float, name: str = "Bitcoin") -> dict:
    return {
        "coin_id": symbol.lower(),
        "symbol": symbol,
        "name": name,
        "image_url": None,
        "price_usd": price,
        "price_change_percentage_24h": None,
        "market_cap_usd": None,
        "volume_24h_usd": None,
        "circulating_supply": None,
        "market_cap_rank": None,
    }


def _tx(symbol: str, tx_type: str, quantity: str, price: str, realized_profit: str | None = None) -> dict:
    return {
        "coin_symbol": symbol,
        "transaction_type": tx_type,
        "quantity": Decimal(quantity),
        "execution_price": Decimal(price),
        "realized_profit": Decimal(realized_profit) if realized_profit is not None else None,
    }


# ---------------------------------------------------------------------------
# Weighted-average-cost replay
# ---------------------------------------------------------------------------


def test_replay_holdings_single_buy():
    holdings = service._replay_holdings([_tx("BTC", "BUY", "1", "20000")])

    assert holdings["BTC"]["quantity"] == Decimal("1")
    assert holdings["BTC"]["avg_cost"] == Decimal("20000")


def test_replay_holdings_two_buys_blend_weighted_average_cost():
    # 1 BTC @ 20000, then 1 BTC @ 30000 -> avg cost (1*20000 + 1*30000) / 2 = 25000
    holdings = service._replay_holdings(
        [_tx("BTC", "BUY", "1", "20000"), _tx("BTC", "BUY", "1", "30000")]
    )

    assert holdings["BTC"]["quantity"] == Decimal("2")
    assert holdings["BTC"]["avg_cost"] == Decimal("25000")


def test_replay_holdings_sell_does_not_change_average_cost():
    holdings = service._replay_holdings(
        [_tx("BTC", "BUY", "2", "20000"), _tx("BTC", "SELL", "1", "30000", "10000")]
    )

    assert holdings["BTC"]["quantity"] == Decimal("1")
    assert holdings["BTC"]["avg_cost"] == Decimal("20000")  # unchanged by the sell


def test_replay_holdings_fully_sold_symbol_is_dropped():
    holdings = service._replay_holdings(
        [_tx("BTC", "BUY", "1", "20000"), _tx("BTC", "SELL", "1", "25000", "5000")]
    )

    assert "BTC" not in holdings


def test_replay_holdings_tracks_multiple_symbols_independently():
    holdings = service._replay_holdings(
        [_tx("BTC", "BUY", "1", "20000"), _tx("ETH", "BUY", "10", "2000")]
    )

    assert holdings["BTC"]["quantity"] == Decimal("1")
    assert holdings["ETH"]["quantity"] == Decimal("10")
    assert holdings["ETH"]["avg_cost"] == Decimal("2000")


# ---------------------------------------------------------------------------
# Buy
# ---------------------------------------------------------------------------


def test_buy_rejects_insufficient_cash(monkeypatch):
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account(cash_balance=Decimal("100")))
    monkeypatch.setattr(
        service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {"BTC": _snapshot("BTC", 20000.0)}
    )
    monkeypatch.setattr(service.repo, "lock_account", lambda conn, account_id: _account(cash_balance=Decimal("100")))

    with pytest.raises(service.InsufficientCashError):
        service.buy(None, "BTC", Decimal("1"))


def test_buy_rejects_unknown_symbol(monkeypatch):
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account())
    monkeypatch.setattr(service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {})

    with pytest.raises(service.UnknownCoinSymbolError):
        service.buy(None, "ZZZ", Decimal("1"))


def test_buy_success_deducts_cash_and_records_transaction(monkeypatch):
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account())
    monkeypatch.setattr(
        service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {"BTC": _snapshot("BTC", 20000.0)}
    )
    monkeypatch.setattr(service.repo, "lock_account", lambda conn, account_id: _account())

    captured = {}

    def _record_balance(conn, account_id, new_balance):
        captured["new_balance"] = new_balance

    def _record_transaction(conn, account_id, coin_symbol, tx_type, quantity, execution_price, total_value, realized_profit):
        return {
            "id": 1,
            "account_id": account_id,
            "coin_symbol": coin_symbol,
            "transaction_type": tx_type,
            "quantity": quantity,
            "execution_price": execution_price,
            "total_value": total_value,
            "realized_profit": realized_profit,
            "executed_at": NOW,
        }

    monkeypatch.setattr(service.repo, "update_cash_balance", _record_balance)
    monkeypatch.setattr(service.repo, "insert_transaction", _record_transaction)

    result = service.buy(None, "btc", Decimal("0.5"))

    assert result["coin_symbol"] == "BTC"
    assert result["total_value"] == Decimal("10000.00")
    assert result["realized_profit"] is None
    assert captured["new_balance"] == Decimal("100000.00") - Decimal("10000.00")


def test_buy_propagates_repo_failure_for_atomic_rollback(monkeypatch):
    """buy() must not swallow a downstream DB failure: atomicity comes from the request-scoped
    connection context manager (paper_trading_routes._get_db) rolling back everything when an
    exception propagates out of the route, so the balance update and transaction insert either
    both land or neither does."""
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account())
    monkeypatch.setattr(
        service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {"BTC": _snapshot("BTC", 20000.0)}
    )
    monkeypatch.setattr(service.repo, "lock_account", lambda conn, account_id: _account())
    monkeypatch.setattr(service.repo, "update_cash_balance", lambda conn, account_id, new_balance: None)

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(service.repo, "insert_transaction", _raise)

    with pytest.raises(RuntimeError):
        service.buy(None, "BTC", Decimal("1"))


# ---------------------------------------------------------------------------
# Sell
# ---------------------------------------------------------------------------


def test_sell_rejects_insufficient_holdings(monkeypatch):
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account())
    monkeypatch.setattr(
        service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {"BTC": _snapshot("BTC", 20000.0)}
    )
    monkeypatch.setattr(service.repo, "lock_account", lambda conn, account_id: _account())
    monkeypatch.setattr(service.repo, "list_transactions_chronological", lambda conn, account_id: [])

    with pytest.raises(service.InsufficientHoldingsError):
        service.sell(None, "BTC", Decimal("1"))


def test_sell_rejects_unknown_symbol(monkeypatch):
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account())
    monkeypatch.setattr(service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {})

    with pytest.raises(service.UnknownCoinSymbolError):
        service.sell(None, "ZZZ", Decimal("1"))


def test_sell_computes_realized_profit_against_weighted_average_cost(monkeypatch):
    # Held 1 BTC at avg cost 20000; sell 0.5 at current price 30000 -> realized = (30000-20000)*0.5
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account())
    monkeypatch.setattr(
        service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {"BTC": _snapshot("BTC", 30000.0)}
    )
    monkeypatch.setattr(service.repo, "lock_account", lambda conn, account_id: _account())
    monkeypatch.setattr(
        service.repo,
        "list_transactions_chronological",
        lambda conn, account_id: [_tx("BTC", "BUY", "1", "20000")],
    )

    captured = {}
    monkeypatch.setattr(
        service.repo, "update_cash_balance", lambda conn, account_id, new_balance: captured.setdefault("balance", new_balance)
    )

    def _record_transaction(conn, account_id, coin_symbol, tx_type, quantity, execution_price, total_value, realized_profit):
        captured["realized_profit"] = realized_profit
        return {
            "id": 2,
            "account_id": account_id,
            "coin_symbol": coin_symbol,
            "transaction_type": tx_type,
            "quantity": quantity,
            "execution_price": execution_price,
            "total_value": total_value,
            "realized_profit": realized_profit,
            "executed_at": NOW,
        }

    monkeypatch.setattr(service.repo, "insert_transaction", _record_transaction)

    result = service.sell(None, "btc", Decimal("0.5"))

    assert captured["realized_profit"] == Decimal("5000.00")
    assert result["total_value"] == Decimal("15000.00")


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def test_reset_account_restores_initial_cash(monkeypatch):
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account(cash_balance=Decimal("42.00")))
    monkeypatch.setattr(
        service.repo, "reset_account", lambda conn, account_id: _account(cash_balance=Decimal("100000.00"))
    )

    result = service.reset_account(None)

    assert result["cash_balance"] == Decimal("100000.00")


# ---------------------------------------------------------------------------
# Portfolio valuation
# ---------------------------------------------------------------------------


def test_get_portfolio_unrealized_and_allocation(monkeypatch):
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account(cash_balance=Decimal("90000")))
    monkeypatch.setattr(
        service.repo,
        "list_transactions_chronological",
        lambda conn, account_id: [_tx("BTC", "BUY", "1", "20000")],
    )
    monkeypatch.setattr(
        service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {"BTC": _snapshot("BTC", 30000.0)}
    )

    portfolio = service.get_portfolio(None)

    assert portfolio["holdings"][0]["unrealized_profit"] == Decimal("10000")
    assert portfolio["total_equity"] == Decimal("90000") + Decimal("30000")
    assert portfolio["best_performer"] == "BTC"
    assert portfolio["worst_performer"] == "BTC"


def test_get_portfolio_empty_account(monkeypatch):
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account())
    monkeypatch.setattr(service.repo, "list_transactions_chronological", lambda conn, account_id: [])
    monkeypatch.setattr(service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {})

    portfolio = service.get_portfolio(None)

    assert portfolio["holdings"] == []
    assert portfolio["total_equity"] == Decimal("100000.00")
    assert portfolio["realized_profit"] == Decimal(0)
    assert portfolio["best_performer"] is None
    assert portfolio["worst_performer"] is None
