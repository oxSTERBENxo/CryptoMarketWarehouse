from datetime import datetime, timezone

import pytest
import requests

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


def test_fetch_coin_market_chart_parses_aligned_series(monkeypatch):
    body = {
        "prices": [[1_753_300_800_000, 65000.0], [1_753_301_100_000, 65100.0]],
        "market_caps": [[1_753_300_800_000, 1_300_000_000_000.0], [1_753_301_100_000, 1_302_000_000_000.0]],
        "total_volumes": [[1_753_300_800_000, 29_000_000_000.0], [1_753_301_100_000, 29_100_000_000.0]],
    }
    monkeypatch.setattr(requests, "get", lambda url, params, timeout: _FakeResponse(body))

    observations = coingecko.fetch_coin_market_chart("bitcoin", days=1)

    assert len(observations) == 2
    assert observations[0].price_usd == 65000.0
    assert observations[0].market_cap_usd == 1_300_000_000_000.0
    assert observations[0].volume_24h_usd == 29_000_000_000.0
    assert observations[0].observation_timestamp == datetime.fromtimestamp(1_753_300_800, tz=timezone.utc)


def test_fetch_coin_market_chart_leaves_unmatched_series_as_none(monkeypatch):
    """CoinGecko's three series aren't guaranteed to share every timestamp -- a price point with
    no matching market_cap/volume entry must come back None, never estimated."""
    body = {
        "prices": [[1_753_300_800_000, 65000.0]],
        "market_caps": [],
        "total_volumes": [[1_753_301_100_000, 29_100_000_000.0]],  # different timestamp
    }
    monkeypatch.setattr(requests, "get", lambda url, params, timeout: _FakeResponse(body))

    observations = coingecko.fetch_coin_market_chart("bitcoin", days=1)

    assert len(observations) == 1
    assert observations[0].market_cap_usd is None
    assert observations[0].volume_24h_usd is None


def test_fetch_coin_market_chart_raises_on_non_dict_response(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, params, timeout: _FakeResponse([1, 2, 3]))

    with pytest.raises(coingecko.CoinGeckoAPIError):
        coingecko.fetch_coin_market_chart("bitcoin", days=1)


def test_fetch_coin_market_chart_maps_403_to_access_restricted(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, params, timeout: _FakeResponse({}, status_code=403))

    with pytest.raises(coingecko.CoinGeckoAccessRestrictedError):
        coingecko.fetch_coin_market_chart("bitcoin", days=1)
