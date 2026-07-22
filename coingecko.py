import requests
from pydantic import BaseModel, ValidationError

MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
REQUEST_TIMEOUT_SECONDS = 10


class CoinGeckoAPIError(Exception):
    """Raised when the CoinGecko API cannot be reached or returns an unexpected response."""


class CoinMarketData(BaseModel):
    id: str
    symbol: str
    name: str
    current_price: float
    market_cap: float | None = None
    market_cap_rank: int | None = None
    total_volume: float | None = None
    circulating_supply: float | None = None


def _request_markets(vs_currency: str, limit: int, order: str) -> list[dict]:
    params = {
        "vs_currency": vs_currency,
        "order": order,
        "per_page": limit,
        "page": 1,
        "sparkline": "false",
    }
    try:
        response = requests.get(MARKETS_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise CoinGeckoAPIError(
            f"CoinGecko request timed out after {REQUEST_TIMEOUT_SECONDS}s"
        ) from exc
    except requests.exceptions.HTTPError as exc:
        raise CoinGeckoAPIError(f"CoinGecko returned an HTTP error: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise CoinGeckoAPIError(f"Failed to reach CoinGecko: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise CoinGeckoAPIError("CoinGecko response was not valid JSON") from exc

    if not isinstance(data, list):
        raise CoinGeckoAPIError(f"Expected a JSON list from CoinGecko, got {type(data).__name__}")

    return data


def fetch_top_markets(
    vs_currency: str = "usd",
    limit: int = 10,
    order: str = "market_cap_desc",
) -> list[CoinMarketData]:
    """Fetch current market data for the top `limit` coins by `order`, quoted in `vs_currency`."""
    raw_coins = _request_markets(vs_currency=vs_currency, limit=limit, order=order)

    try:
        return [CoinMarketData.model_validate(coin) for coin in raw_coins]
    except ValidationError as exc:
        raise CoinGeckoAPIError(f"CoinGecko response did not match the expected shape: {exc}") from exc
