import argparse
import sys

from coingecko import CoinGeckoAPIError, fetch_top_markets


def format_price(price: float) -> str:
    if price >= 1:
        return f"${price:,.2f}"
    return f"${price:.6f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch current crypto market data from CoinGecko.")
    parser.add_argument("--currency", default="usd", help="Quote currency (default: usd)")
    parser.add_argument("--limit", type=int, default=10, help="Number of coins to fetch (default: 10)")
    parser.add_argument("--order", default="market_cap_desc", help="CoinGecko ordering (default: market_cap_desc)")
    args = parser.parse_args()

    try:
        coins = fetch_top_markets(vs_currency=args.currency, limit=args.limit, order=args.order)
    except CoinGeckoAPIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    name_width = max((len(coin.name) for coin in coins), default=0)
    for coin in coins:
        print(f"{coin.name:<{name_width}} {format_price(coin.current_price)}")


if __name__ == "__main__":
    main()
