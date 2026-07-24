from datetime import date, datetime, timezone

import requests
from pydantic import BaseModel, Field, ValidationError

MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
HISTORY_URL = "https://api.coingecko.com/api/v3/coins/{id}/history"
MARKET_CHART_URL = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"
REQUEST_TIMEOUT_SECONDS = 10


class CoinGeckoAPIError(Exception):
    """Raised when the CoinGecko API cannot be reached or returns an unexpected response."""


class CoinGeckoAccessRestrictedError(CoinGeckoAPIError):
    """Raised on HTTP 401/403 from CoinGecko: the free/demo tier hard-restricts endpoints like
    `/coins/{id}/history` to a rolling recent window (observed: a request for a date far in the
    past is rejected outright, not rate-limited). This is a permanent rejection of the specific
    request, not a transient failure, so callers should not retry it."""


class CoinMarketData(BaseModel):
    id: str
    symbol: str
    name: str
    current_price: float = Field(ge=0)
    market_cap: float | None = Field(default=None, ge=0)
    market_cap_rank: int | None = Field(default=None, gt=0)
    total_volume: float | None = Field(default=None, ge=0)
    circulating_supply: float | None = Field(default=None, ge=0)
    image: str | None = None
    price_change_percentage_24h: float | None = None


class CoinIntradayObservation(BaseModel):
    """One timestamped observation from `/coins/{id}/market_chart`, as used for the "Today"
    intraday chart. `market_cap_usd`/`volume_24h_usd` are `None` when CoinGecko's response omits
    that series for a given timestamp (observed to happen occasionally) -- never estimated."""

    observation_timestamp: datetime
    price_usd: float = Field(ge=0)
    market_cap_usd: float | None = Field(default=None, ge=0)
    volume_24h_usd: float | None = Field(default=None, ge=0)


class CoinHistorySnapshot(BaseModel):
    """One coin's market data on one specific past calendar date, from `/coins/{id}/history`.

    That endpoint never reports `circulating_supply`, and only sometimes reports
    `market_cap_rank` for historical dates — both stay `None` when absent, same as the nullable
    `dw.fact_market_snapshot` columns they eventually populate.
    """

    id: str
    symbol: str
    name: str
    current_price: float = Field(ge=0)
    market_cap: float | None = Field(default=None, ge=0)
    market_cap_rank: int | None = Field(default=None, gt=0)
    total_volume: float | None = Field(default=None, ge=0)


def _get_json(url: str, params: dict) -> dict | list:
    """Shared GET + error-mapping for every CoinGecko call: network/timeout/HTTP/non-JSON
    failures all surface as CoinGeckoAPIError so callers don't need requests-specific handling."""
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise CoinGeckoAPIError(
            f"CoinGecko request timed out after {REQUEST_TIMEOUT_SECONDS}s"
        ) from exc
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in (401, 403):
            raise CoinGeckoAccessRestrictedError(
                f"CoinGecko rejected the request ({exc.response.status_code}), likely outside the "
                f"free-tier's allowed history window: {exc}"
            ) from exc
        raise CoinGeckoAPIError(f"CoinGecko returned an HTTP error: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise CoinGeckoAPIError(f"Failed to reach CoinGecko: {exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise CoinGeckoAPIError("CoinGecko response was not valid JSON") from exc


def _request_markets(vs_currency: str, limit: int, order: str) -> list[dict]:
    params = {
        "vs_currency": vs_currency,
        "order": order,
        "per_page": limit,
        "page": 1,
        "sparkline": "false",
    }
    data = _get_json(MARKETS_URL, params)
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


def fetch_coin_history(coin_id: str, on_date: date, vs_currency: str = "usd") -> CoinHistorySnapshot | None:
    """Fetch one coin's market data on one specific past calendar date via `/coins/{id}/history`.

    Used by the historical backfill pipeline (`etl/backfill_market_history.py`) instead of
    `fetch_top_markets`: this endpoint is the only free, keyless CoinGecko endpoint that returns
    an exact single calendar day per call, matching the warehouse's daily `(date_key, coin_key)`
    grain. Returns None (not an error) if CoinGecko has no market data for that coin on that date
    (e.g. the coin didn't exist yet) — a real "no data" outcome, distinct from a request failure.
    Raises CoinGeckoAPIError for network/HTTP/shape failures, same as fetch_top_markets.
    """
    params = {"date": on_date.strftime("%d-%m-%Y"), "localization": "false"}
    data = _get_json(HISTORY_URL.format(id=coin_id), params)
    if not isinstance(data, dict):
        raise CoinGeckoAPIError(f"Expected a JSON object from CoinGecko, got {type(data).__name__}")

    market_data = data.get("market_data") or {}
    price = (market_data.get("current_price") or {}).get(vs_currency)
    if price is None:
        return None

    try:
        return CoinHistorySnapshot.model_validate(
            {
                "id": data.get("id", coin_id),
                "symbol": data.get("symbol", ""),
                "name": data.get("name", ""),
                "current_price": price,
                "market_cap": (market_data.get("market_cap") or {}).get(vs_currency),
                "market_cap_rank": data.get("market_cap_rank"),
                "total_volume": (market_data.get("total_volume") or {}).get(vs_currency),
            }
        )
    except ValidationError as exc:
        raise CoinGeckoAPIError(f"CoinGecko response did not match the expected shape: {exc}") from exc


def fetch_coin_market_chart(
    coin_id: str, days: int = 1, vs_currency: str = "usd"
) -> list[CoinIntradayObservation]:
    """Fetch sub-daily market data via `/coins/{id}/market_chart?days={days}`, the only free,
    keyless CoinGecko endpoint that returns multiple observations for the current day (used for
    the "Today" intraday chart, distinct from `fetch_coin_history`'s one-exact-day-per-call shape
    that backs the daily warehouse grain).

    CoinGecko returns three independently-indexed `[timestamp_ms, value]` arrays (`prices`,
    `market_caps`, `total_volumes`); they are usually aligned but that isn't guaranteed, so
    market_cap/volume are looked up by exact millisecond timestamp rather than positionally
    zipped, and are left `None` for a `prices` timestamp with no match (never estimated).
    """
    params = {"vs_currency": vs_currency, "days": days}
    data = _get_json(MARKET_CHART_URL.format(id=coin_id), params)
    if not isinstance(data, dict):
        raise CoinGeckoAPIError(f"Expected a JSON object from CoinGecko, got {type(data).__name__}")

    prices = data.get("prices") or []
    market_caps = {int(ts): value for ts, value in (data.get("market_caps") or [])}
    volumes = {int(ts): value for ts, value in (data.get("total_volumes") or [])}

    try:
        observations = []
        for ts, price in prices:
            ts_ms = int(ts)
            observations.append(
                CoinIntradayObservation(
                    observation_timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
                    price_usd=price,
                    market_cap_usd=market_caps.get(ts_ms),
                    volume_24h_usd=volumes.get(ts_ms),
                )
            )
        return observations
    except (ValidationError, TypeError, ValueError) as exc:
        raise CoinGeckoAPIError(f"CoinGecko response did not match the expected shape: {exc}") from exc
