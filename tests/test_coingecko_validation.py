"""Regression tests for the non-negative/positive-rank value validation added to the CoinGecko
Pydantic models (CoinMarketData, CoinIntradayObservation, CoinHistorySnapshot). Before this, a
malformed or corrupted CoinGecko response with a negative price/market_cap/volume or a
non-positive rank would have been accepted and passed straight through into staging."""

from datetime import date, datetime, timezone

import requests
from pydantic import ValidationError

from integrations import coingecko


class _FakeResponse:
    def __init__(self, json_body, status_code=200):
        self._json_body = json_body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.exceptions.HTTPError(response=response)

    def json(self):
        return self._json_body


def test_fetch_top_markets_rejects_negative_price(monkeypatch):
    body = [{"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "current_price": -1.0}]
    monkeypatch.setattr(requests, "get", lambda url, params, timeout: _FakeResponse(body))

    try:
        coingecko.fetch_top_markets()
        assert False, "expected CoinGeckoAPIError for a negative price"
    except coingecko.CoinGeckoAPIError as exc:
        assert "current_price" in str(exc)


def test_fetch_top_markets_rejects_non_positive_rank(monkeypatch):
    body = [
        {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "current_price": 65000.0,
            "market_cap_rank": 0,
        }
    ]
    monkeypatch.setattr(requests, "get", lambda url, params, timeout: _FakeResponse(body))

    try:
        coingecko.fetch_top_markets()
        assert False, "expected CoinGeckoAPIError for a non-positive rank"
    except coingecko.CoinGeckoAPIError as exc:
        assert "market_cap_rank" in str(exc)


def test_fetch_top_markets_accepts_zero_price():
    """Zero is a legitimate (if unusual) price for a worthless token -- only negative values and
    non-positive ranks are rejected."""
    coin = coingecko.CoinMarketData(id="x", symbol="x", name="X", current_price=0.0)
    assert coin.current_price == 0.0


def test_fetch_coin_history_rejects_negative_market_cap(monkeypatch):
    body = {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "market_data": {
            "current_price": {"usd": 65000.0},
            "market_cap": {"usd": -5.0},
        },
    }
    monkeypatch.setattr(requests, "get", lambda url, params, timeout: _FakeResponse(body))

    try:
        coingecko.fetch_coin_history("bitcoin", on_date=date(2026, 1, 1))
        assert False, "expected CoinGeckoAPIError for a negative market cap"
    except coingecko.CoinGeckoAPIError as exc:
        assert "market_cap" in str(exc)


def test_intraday_observation_rejects_negative_volume():
    try:
        coingecko.CoinIntradayObservation(
            observation_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            price_usd=65000.0,
            volume_24h_usd=-1.0,
        )
        assert False, "expected ValidationError for a negative volume"
    except ValidationError as exc:
        assert "volume_24h_usd" in str(exc)
