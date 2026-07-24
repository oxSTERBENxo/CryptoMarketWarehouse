from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from portfolio import routes as portfolio_routes
from portfolio import service
from main import app

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _portfolio_detail(**overrides) -> dict:
    detail = {
        "id": 1,
        "name": "My Portfolio",
        "description": None,
        "created_at": NOW,
        "updated_at": NOW,
        "holdings": [],
        "summary": {
            "total_value": 0.0,
            "total_cost_basis": 0.0,
            "total_unrealized_profit": 0.0,
            "total_unrealized_percent": None,
        },
    }
    detail.update(overrides)
    return detail


def _holding(**overrides) -> dict:
    holding = {
        "id": 1,
        "portfolio_id": 1,
        "coin_symbol": "BTC",
        "coin_name": "Bitcoin",
        "quantity": 1.0,
        "average_buy_price": 20000.0,
        "current_price": 30000.0,
        "current_value": 30000.0,
        "cost_basis": 20000.0,
        "unrealized_profit": 10000.0,
        "profit_percent": 50.0,
        "created_at": NOW,
        "updated_at": NOW,
    }
    holding.update(overrides)
    return holding


def _override_db():
    yield object()


@pytest.fixture(autouse=True)
def _stub_db():
    app.dependency_overrides[portfolio_routes._get_db] = _override_db
    yield
    del app.dependency_overrides[portfolio_routes._get_db]


client = TestClient(app)


def test_list_portfolios(monkeypatch):
    monkeypatch.setattr(service, "list_portfolios", lambda conn: [_portfolio_detail()])

    response = client.get("/portfolios")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "My Portfolio"


def test_create_portfolio(monkeypatch):
    monkeypatch.setattr(service, "create_portfolio", lambda conn, name, description: _portfolio_detail(name=name))

    response = client.post("/portfolios", json={"name": "New Portfolio"})

    assert response.status_code == 201
    assert response.json()["name"] == "New Portfolio"


def test_create_portfolio_rejects_blank_name():
    response = client.post("/portfolios", json={"name": "   "})

    assert response.status_code == 422


def test_get_portfolio_returns_404(monkeypatch):
    def _raise(conn, portfolio_id):
        raise service.PortfolioNotFoundError(portfolio_id)

    monkeypatch.setattr(service, "get_portfolio", _raise)

    response = client.get("/portfolios/999")

    assert response.status_code == 404


def test_delete_portfolio_cascades_via_service(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "delete_portfolio", lambda conn, portfolio_id: calls.append(portfolio_id))

    response = client.delete("/portfolios/1")

    assert response.status_code == 204
    assert calls == [1]


def test_add_holding_rejects_unknown_symbol(monkeypatch):
    def _raise(conn, portfolio_id, coin_symbol, quantity, average_buy_price):
        raise service.UnknownCoinSymbolError(coin_symbol)

    monkeypatch.setattr(service, "add_holding", _raise)

    response = client.post("/portfolios/1/holdings", json={"coin_symbol": "ZZZ", "quantity": 1, "average_buy_price": 1})

    assert response.status_code == 400


def test_add_holding_rejects_duplicate_symbol(monkeypatch):
    def _raise(conn, portfolio_id, coin_symbol, quantity, average_buy_price):
        raise service.DuplicateHoldingError(portfolio_id, coin_symbol)

    monkeypatch.setattr(service, "add_holding", _raise)

    response = client.post("/portfolios/1/holdings", json={"coin_symbol": "BTC", "quantity": 1, "average_buy_price": 1})

    assert response.status_code == 400


def test_add_holding_rejects_negative_quantity():
    response = client.post("/portfolios/1/holdings", json={"coin_symbol": "BTC", "quantity": -1, "average_buy_price": 1})

    assert response.status_code == 422


def test_add_holding_rejects_zero_quantity():
    response = client.post("/portfolios/1/holdings", json={"coin_symbol": "BTC", "quantity": 0, "average_buy_price": 1})

    assert response.status_code == 422


def test_add_holding_success(monkeypatch):
    monkeypatch.setattr(
        service,
        "add_holding",
        lambda conn, portfolio_id, coin_symbol, quantity, average_buy_price: _holding(),
    )

    response = client.post("/portfolios/1/holdings", json={"coin_symbol": "btc", "quantity": 1, "average_buy_price": 20000})

    assert response.status_code == 201
    body = response.json()
    assert body["current_value"] == 30000.0
    assert body["profit_percent"] == 50.0


def test_update_holding_returns_404(monkeypatch):
    def _raise(conn, holding_id, quantity, average_buy_price):
        raise service.HoldingNotFoundError(holding_id)

    monkeypatch.setattr(service, "edit_holding", _raise)

    response = client.put("/holdings/999", json={"quantity": 1, "average_buy_price": 1})

    assert response.status_code == 404


def test_delete_holding_returns_404(monkeypatch):
    def _raise(conn, holding_id):
        raise service.HoldingNotFoundError(holding_id)

    monkeypatch.setattr(service, "remove_holding", _raise)

    response = client.delete("/holdings/999")

    assert response.status_code == 404


def test_delete_holding_success(monkeypatch):
    monkeypatch.setattr(service, "remove_holding", lambda conn, holding_id: None)

    response = client.delete("/holdings/1")

    assert response.status_code == 204
