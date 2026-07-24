import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CoinSelect } from "./CoinSelect";
import * as analyticsApi from "../api/analytics";
import type { CurrentMarketCoin, CurrentMarketSnapshot } from "../api/types";

function coin(overrides: Partial<CurrentMarketCoin> = {}): CurrentMarketCoin {
  return {
    coin_id: "bitcoin",
    symbol: "btc",
    name: "Bitcoin",
    image_url: "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
    price_usd: 65160.0,
    price_change_percentage_24h: 1.84,
    market_cap_usd: 1_000_000_000,
    volume_24h_usd: 500_000_000,
    circulating_supply: 19_000_000,
    market_cap_rank: 1,
    ...overrides,
  };
}

function snapshot(coins: CurrentMarketCoin[]): CurrentMarketSnapshot {
  return {
    refreshed_at: "2026-07-24T00:00:00Z",
    coin_count: coins.length,
    total_market_cap_usd: 0,
    total_volume_24h_usd: 0,
    coins,
  };
}

async function openDropdown() {
  const input = screen.getByRole("combobox");
  fireEvent.focus(input);
  await screen.findByRole("listbox");
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("CoinSelect", () => {
  it("renders logo, price, and 24h percent for each option", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(snapshot([coin()]));
    render(<CoinSelect value="" onChange={vi.fn()} />);

    await openDropdown();

    expect(screen.getByRole("option", { name: /Bitcoin/ })).toBeInTheDocument();
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("$65,160.00")).toBeInTheDocument();
    expect(screen.getByText(/\+1\.84%/)).toBeInTheDocument();
  });

  it("gives a positive 24h change positive styling", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(
      snapshot([coin({ price_change_percentage_24h: 1.84 })])
    );
    render(<CoinSelect value="" onChange={vi.fn()} />);
    await openDropdown();

    expect(screen.getByText(/\+1\.84%/)).toHaveClass("profit-positive");
  });

  it("gives a negative 24h change negative styling", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(
      snapshot([coin({ price_change_percentage_24h: -2.31 })])
    );
    render(<CoinSelect value="" onChange={vi.fn()} />);
    await openDropdown();

    expect(screen.getByText(/-2\.31%/)).toHaveClass("profit-negative");
  });

  it("gives exactly zero neutral styling", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(
      snapshot([coin({ price_change_percentage_24h: 0 })])
    );
    render(<CoinSelect value="" onChange={vi.fn()} />);
    await openDropdown();

    expect(screen.getByText("0.00%")).toHaveClass("profit-neutral");
  });

  it("renders a placeholder when 24h change is unavailable", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(
      snapshot([coin({ price_change_percentage_24h: null })])
    );
    render(<CoinSelect value="" onChange={vi.fn()} />);
    await openDropdown();

    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("selects the coin when clicking empty padding inside the row", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(snapshot([coin()]));
    const onChange = vi.fn();
    render(<CoinSelect value="" onChange={onChange} />);
    await openDropdown();

    // Click the identity wrapper (blank space beside the text), not the name text node itself.
    const option = screen.getByRole("option", { name: /Bitcoin/ });
    fireEvent.click(option);

    expect(onChange).toHaveBeenCalledWith("BTC");
  });

  it("selects the coin when clicking the logo", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(snapshot([coin()]));
    const onChange = vi.fn();
    render(<CoinSelect value="" onChange={onChange} />);
    await openDropdown();

    const option = screen.getByRole("option", { name: /Bitcoin/ });
    const logo = option.querySelector(".coin-logo") as HTMLElement;
    fireEvent.click(logo);

    expect(onChange).toHaveBeenCalledWith("BTC");
  });

  it("selects a focused option on Enter, exactly once", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(snapshot([coin()]));
    const onChange = vi.fn();
    render(<CoinSelect value="" onChange={onChange} />);
    await openDropdown();

    const option = screen.getByRole("option", { name: /Bitcoin/ });
    option.focus();
    fireEvent.keyDown(option, { key: "Enter" });

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("BTC");
  });

  it("sorts ranked coins ascending by market-cap rank, then unranked coins alphabetically", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(
      snapshot([
        coin({ coin_id: "eth", symbol: "eth", name: "Ethereum", market_cap_rank: 2 }),
        coin({ coin_id: "zeta", symbol: "zzz", name: "Zeta Coin", market_cap_rank: null }),
        coin({ coin_id: "bitcoin", symbol: "btc", name: "Bitcoin", market_cap_rank: 1 }),
        coin({ coin_id: "aaa", symbol: "aaa", name: "Aaa Coin", market_cap_rank: null }),
      ])
    );
    render(<CoinSelect value="" onChange={vi.fn()} />);
    await openDropdown();

    const names = screen.getAllByRole("option").map((el) => el.textContent);
    // Ranked ascending (Bitcoin #1, Ethereum #2) first, then unranked alphabetically (Aaa, Zeta).
    expect(names[0]).toMatch(/Bitcoin/);
    expect(names[1]).toMatch(/Ethereum/);
    expect(names[2]).toMatch(/Aaa Coin/);
    expect(names[3]).toMatch(/Zeta Coin/);
  });

  it("filters options by name/symbol search while preserving order", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(
      snapshot([coin(), coin({ coin_id: "ethereum", symbol: "eth", name: "Ethereum", market_cap_rank: 2 })])
    );
    render(<CoinSelect value="" onChange={vi.fn()} />);
    await openDropdown();

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "eth" } });

    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(1));
    expect(screen.getByRole("option", { name: /Ethereum/ })).toBeInTheDocument();
  });

  it("only offers restrictToSymbols coins (Sell picker scoping)", async () => {
    vi.spyOn(analyticsApi, "getCurrentMarket").mockResolvedValue(
      snapshot([coin(), coin({ coin_id: "ethereum", symbol: "eth", name: "Ethereum", market_cap_rank: 2 })])
    );
    render(<CoinSelect value="" onChange={vi.fn()} restrictToSymbols={["ETH"]} />);
    await openDropdown();

    expect(screen.queryByRole("option", { name: /Bitcoin/ })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Ethereum/ })).toBeInTheDocument();
  });
});
