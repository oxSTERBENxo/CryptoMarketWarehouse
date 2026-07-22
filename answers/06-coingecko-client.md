# Milestone: CoinGecko Client

## Design

Single client module, `coingecko.py`, exposing one public function `fetch_top_markets(vs_currency, limit, order)` calling the official `/coins/markets` endpoint via `requests` (new minimal dependency).

Split into two stages to keep the raw API response separate from the parsed model:
- `_request_markets(...)` — HTTP call, `raise_for_status()`, basic shape check (valid JSON? a list?) — returns raw `list[dict]`.
- `fetch_top_markets(...)` — calls that, then maps each raw dict through the `CoinMarketData` Pydantic model (Pydantic already a transitive dependency of FastAPI, reused here for structural validation instead of hand-rolled field checks).

All failure modes (timeout, HTTP error, malformed JSON, response not matching the expected shape) are normalized into one exception type, `CoinGeckoAPIError`, with a distinct clear message per cause.

`CoinMarketData` only carries fields relevant to this project: `id`/`symbol`/`name` (matches `dw.dim_coin`'s natural key/attributes) and `current_price`/`market_cap`/`market_cap_rank`/`total_volume`/`circulating_supply` (matches `dw.fact_market_snapshot`'s measures) — not CoinGecko's full payload.

`coingecko_cli.py` is a thin argparse wrapper around the client for manual/demo use.

## Files created

| File | Purpose |
|---|---|
| `coingecko.py` | Client module: `CoinMarketData` (Pydantic model), `CoinGeckoAPIError`, `fetch_top_markets()`. |
| `coingecko_cli.py` | CLI: `--currency`, `--limit`, `--order` flags, prints an aligned name/price summary. |
| `requirements.txt` | Added `requests==2.34.2`. |

## Reuse by future ETL

Future ETL code will `from coingecko import fetch_top_markets, CoinMarketData, CoinGeckoAPIError` and call `fetch_top_markets(limit=..., vs_currency="usd")` to get a list of typed `CoinMarketData` objects — no HTTP/JSON handling needed in ETL code. The ETL layer's only job will be mapping `CoinMarketData` fields into staging rows (and eventually into `dw.dim_coin`/`dw.fact_market_snapshot` via the existing SCD2/grain logic) and catching `CoinGeckoAPIError` to log failures into `audit.etl_run`. The client has zero database or ETL knowledge, so it stays reusable without modification.

## Live API verification

- `coingecko_cli.py --limit 5` — succeeded, returned real current prices for Bitcoin/Ethereum/Tether/BNB/USDC.
- `--currency eur --limit 3 --order volume_desc` — confirmed currency and ordering are both configurable and reflected in live results.
- `--currency not_a_real_currency` — CoinGecko returned `400 Bad Request`, caught and reported as `Error: CoinGecko returned an HTTP error: 400 Client Error...`, exit code 1.
- Forced a near-zero timeout via a small script — caught and reported as `CoinGecko request timed out after 0.001s`.

**Confirmed: tested against the live CoinGecko API, including both success and error paths.**

## Example output

```
Bitcoin  $65,839.00
Ethereum $1,924.71
Tether   $0.999337
BNB      $569.47
USDC     $0.999848
```
