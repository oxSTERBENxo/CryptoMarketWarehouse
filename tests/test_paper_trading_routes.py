from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from paper_trading import routes as paper_trading_routes
from paper_trading import service
from main import app

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _account(**overrides) -> dict:
    account = {
        "id": 1,
        "name": "Paper Trading Account",
        "initial_cash": 100000.0,
        "cash_balance": 100000.0,
        "created_at": NOW,
        "updated_at": NOW,
    }
    account.update(overrides)
    return account


def _transaction(**overrides) -> dict:
    tx = {
        "id": 1,
        "account_id": 1,
        "coin_symbol": "BTC",
        "transaction_type": "BUY",
        "quantity": 1.0,
        "execution_price": 20000.0,
        "total_value": 20000.0,
        "realized_profit": None,
        "executed_at": NOW,
    }
    tx.update(overrides)
    return tx


def _portfolio(**overrides) -> dict:
    portfolio = {
        "account": _account(),
        "holdings": [],
        "cash_balance": 100000.0,
        "invested_value": 0.0,
        "holdings_value": 0.0,
        "total_equity": 100000.0,
        "realized_profit": 0.0,
        "unrealized_profit": 0.0,
        "total_return_percent": 0.0,
        "best_performer": None,
        "worst_performer": None,
    }
    portfolio.update(overrides)
    return portfolio


def _override_db():
    yield object()


@pytest.fixture(autouse=True)
def _stub_db():
    app.dependency_overrides[paper_trading_routes._get_db] = _override_db
    yield
    del app.dependency_overrides[paper_trading_routes._get_db]


client = TestClient(app)


def test_get_paper_account(monkeypatch):
    monkeypatch.setattr(service, "get_or_create_account", lambda conn: _account())

    response = client.get("/paper-account")

    assert response.status_code == 200
    assert response.json()["cash_balance"] == 100000.0


def test_reset_paper_account(monkeypatch):
    monkeypatch.setattr(service, "reset_account", lambda conn: _account())

    response = client.post("/paper-account/reset")

    assert response.status_code == 200


def test_get_paper_portfolio(monkeypatch):
    monkeypatch.setattr(service, "get_portfolio", lambda conn: _portfolio())

    response = client.get("/paper-portfolio")

    assert response.status_code == 200
    assert response.json()["cash_balance"] == 100000.0


def test_buy_returns_404_for_unknown_symbol(monkeypatch):
    def _raise(conn, coin_symbol, quantity):
        raise service.UnknownCoinSymbolError(coin_symbol)

    monkeypatch.setattr(service, "buy", _raise)

    response = client.post("/paper-trades/buy", json={"coin_symbol": "ZZZ", "quantity": 1})

    assert response.status_code == 404


def test_buy_returns_400_for_insufficient_cash(monkeypatch):
    def _raise(conn, coin_symbol, quantity):
        raise service.InsufficientCashError(coin_symbol, Decimal("999999"), Decimal("100"))

    monkeypatch.setattr(service, "buy", _raise)

    response = client.post("/paper-trades/buy", json={"coin_symbol": "BTC", "quantity": 1})

    assert response.status_code == 400


def test_buy_rejects_zero_quantity_with_422():
    response = client.post("/paper-trades/buy", json={"coin_symbol": "BTC", "quantity": 0})

    assert response.status_code == 422


def test_buy_rejects_negative_quantity_with_422():
    response = client.post("/paper-trades/buy", json={"coin_symbol": "BTC", "quantity": -1})

    assert response.status_code == 422


def test_buy_rejects_blank_symbol_with_422():
    response = client.post("/paper-trades/buy", json={"coin_symbol": "   ", "quantity": 1})

    assert response.status_code == 422


def test_buy_success(monkeypatch):
    monkeypatch.setattr(service, "buy", lambda conn, coin_symbol, quantity: _transaction())

    response = client.post("/paper-trades/buy", json={"coin_symbol": "btc", "quantity": 1})

    assert response.status_code == 201
    assert response.json()["transaction_type"] == "BUY"


def test_sell_returns_400_for_insufficient_holdings(monkeypatch):
    def _raise(conn, coin_symbol, quantity):
        raise service.InsufficientHoldingsError(coin_symbol, Decimal("5"), Decimal("1"))

    monkeypatch.setattr(service, "sell", _raise)

    response = client.post("/paper-trades/sell", json={"coin_symbol": "BTC", "quantity": 5})

    assert response.status_code == 400


def test_sell_returns_404_for_unknown_symbol(monkeypatch):
    def _raise(conn, coin_symbol, quantity):
        raise service.UnknownCoinSymbolError(coin_symbol)

    monkeypatch.setattr(service, "sell", _raise)

    response = client.post("/paper-trades/sell", json={"coin_symbol": "ZZZ", "quantity": 1})

    assert response.status_code == 404


def test_sell_success(monkeypatch):
    monkeypatch.setattr(
        service, "sell", lambda conn, coin_symbol, quantity: _transaction(transaction_type="SELL", realized_profit=500.0)
    )

    response = client.post("/paper-trades/sell", json={"coin_symbol": "btc", "quantity": 1})

    assert response.status_code == 201
    assert response.json()["realized_profit"] == 500.0


def test_list_paper_trades(monkeypatch):
    monkeypatch.setattr(service, "list_transactions", lambda conn, limit: [_transaction()])

    response = client.get("/paper-trades")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_paper_trades_rejects_out_of_range_limit_with_422():
    response = client.get("/paper-trades", params={"limit": 99999})

    assert response.status_code == 422
