from datetime import datetime, timezone

import pytest
from psycopg.errors import UniqueViolation

from portfolio import service

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _holding_row(**overrides) -> dict:
    row = {
        "id": 1,
        "portfolio_id": 1,
        "coin_symbol": "BTC",
        "quantity": 2.0,
        "average_buy_price": 20000.0,
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(overrides)
    return row


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


def test_price_holdings_computes_gain(monkeypatch):
    monkeypatch.setattr(
        service.analytics_repository,
        "fetch_live_prices_for_symbols",
        lambda conn, symbols: {"BTC": _snapshot("BTC", 30000.0)},
    )

    [priced] = service._price_holdings(None, [_holding_row()])

    assert priced["current_price"] == 30000.0
    assert priced["cost_basis"] == 40000.0
    assert priced["current_value"] == 60000.0
    assert priced["unrealized_profit"] == 20000.0
    assert priced["profit_percent"] == 50.0
    assert priced["coin_name"] == "Bitcoin"


def test_price_holdings_computes_loss(monkeypatch):
    monkeypatch.setattr(
        service.analytics_repository,
        "fetch_live_prices_for_symbols",
        lambda conn, symbols: {"BTC": _snapshot("BTC", 15000.0)},
    )

    [priced] = service._price_holdings(None, [_holding_row()])

    assert priced["current_value"] == 30000.0
    assert priced["unrealized_profit"] == -10000.0
    assert priced["profit_percent"] == -25.0


def test_price_holdings_handles_missing_price(monkeypatch):
    monkeypatch.setattr(service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {})

    [priced] = service._price_holdings(None, [_holding_row()])

    assert priced["current_price"] is None
    assert priced["current_value"] is None
    assert priced["unrealized_profit"] is None
    assert priced["profit_percent"] is None
    assert priced["cost_basis"] == 40000.0  # still computable without a market price


def test_price_holdings_handles_zero_cost_basis(monkeypatch):
    monkeypatch.setattr(
        service.analytics_repository,
        "fetch_live_prices_for_symbols",
        lambda conn, symbols: {"BTC": _snapshot("BTC", 30000.0)},
    )

    [priced] = service._price_holdings(None, [_holding_row(average_buy_price=0.0)])

    assert priced["cost_basis"] == 0.0
    assert priced["unrealized_profit"] == 60000.0
    assert priced["profit_percent"] is None  # division by zero avoided, not misreported as 0%


def test_summarize_excludes_unpriced_holdings():
    priced = [
        {"current_value": 60000.0, "cost_basis": 40000.0},
        {"current_value": None, "cost_basis": 5000.0},
    ]

    summary = service._summarize(priced)

    assert summary["total_value"] == 60000.0
    assert summary["total_cost_basis"] == 40000.0
    assert summary["total_unrealized_profit"] == 20000.0
    assert summary["total_unrealized_percent"] == 50.0


def test_summarize_handles_zero_total_cost_basis():
    priced = [{"current_value": 0.0, "cost_basis": 0.0}]

    summary = service._summarize(priced)

    assert summary["total_unrealized_percent"] is None


def test_summarize_empty_portfolio():
    summary = service._summarize([])

    assert summary["total_value"] == 0
    assert summary["total_cost_basis"] == 0
    assert summary["total_unrealized_profit"] == 0
    assert summary["total_unrealized_percent"] is None


def test_list_portfolios_batches_holdings_and_prices_across_all_portfolios(monkeypatch):
    """Regression test for an N+1: list_portfolios used to call list_holdings and
    fetch_live_prices_for_symbols once per portfolio. For N portfolios it must now issue exactly
    one list_portfolios call, one batched holdings call, and one batched prices call -- never N of
    either -- while still returning correctly-priced, per-portfolio holdings and summaries."""
    portfolios = [
        {"id": 1, "name": "Alpha", "description": None, "created_at": NOW, "updated_at": NOW},
        {"id": 2, "name": "Beta", "description": None, "created_at": NOW, "updated_at": NOW},
    ]
    monkeypatch.setattr(service.repo, "list_portfolios", lambda conn: portfolios)

    holdings_calls = []

    def _fake_list_holdings_for_portfolios(conn, portfolio_ids):
        holdings_calls.append(list(portfolio_ids))
        return {
            1: [_holding_row(id=1, portfolio_id=1, coin_symbol="BTC")],
            2: [_holding_row(id=2, portfolio_id=2, coin_symbol="ETH", average_buy_price=1000.0)],
        }

    monkeypatch.setattr(service.repo, "list_holdings_for_portfolios", _fake_list_holdings_for_portfolios)

    price_calls = []

    def _fake_fetch_live_prices(conn, symbols):
        price_calls.append(sorted(symbols))
        return {"BTC": _snapshot("BTC", 30000.0), "ETH": _snapshot("ETH", 2000.0, name="Ethereum")}

    monkeypatch.setattr(service.analytics_repository, "fetch_live_prices_for_symbols", _fake_fetch_live_prices)

    details = service.list_portfolios(None)

    assert len(holdings_calls) == 1
    assert len(price_calls) == 1
    assert holdings_calls[0] == [1, 2]

    [alpha, beta] = details
    assert alpha["id"] == 1
    assert alpha["holdings"][0]["current_price"] == 30000.0
    assert alpha["summary"]["total_value"] == 60000.0
    assert beta["id"] == 2
    assert beta["holdings"][0]["coin_name"] == "Ethereum"


def test_list_portfolios_handles_portfolio_with_no_holdings(monkeypatch):
    monkeypatch.setattr(service.repo, "list_portfolios", lambda conn: [
        {"id": 1, "name": "Empty", "description": None, "created_at": NOW, "updated_at": NOW},
    ])
    monkeypatch.setattr(service.repo, "list_holdings_for_portfolios", lambda conn, portfolio_ids: {1: []})
    monkeypatch.setattr(service.analytics_repository, "fetch_live_prices_for_symbols", lambda conn, symbols: {})

    [detail] = service.list_portfolios(None)

    assert detail["holdings"] == []
    assert detail["summary"]["total_value"] == 0


def test_add_holding_translates_concurrent_duplicate_insert(monkeypatch):
    """A second concurrent request can pass the pre-check before the first commits; the unique
    constraint then rejects the INSERT, which must surface as DuplicateHoldingError (-> 400 at
    the route), not an unhandled UniqueViolation (-> 500)."""
    monkeypatch.setattr(service.repo, "get_portfolio", lambda conn, portfolio_id: {"id": portfolio_id})
    monkeypatch.setattr(service.repo, "holding_exists_for_symbol", lambda conn, portfolio_id, coin_symbol: False)
    monkeypatch.setattr(
        service.analytics_repository,
        "fetch_live_prices_for_symbols",
        lambda conn, symbols: {"BTC": _snapshot("BTC", 30000.0)},
    )

    def _raise_unique_violation(conn, portfolio_id, coin_symbol, quantity, average_buy_price):
        raise UniqueViolation("duplicate key value violates unique constraint")

    monkeypatch.setattr(service.repo, "create_holding", _raise_unique_violation)

    with pytest.raises(service.DuplicateHoldingError):
        service.add_holding(None, 1, "BTC", 1.0, 20000.0)
