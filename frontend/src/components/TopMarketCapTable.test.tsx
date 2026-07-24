import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TopMarketCapTable } from "./TopMarketCapTable";
import type { CurrentMarketCoin } from "../api/types";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

const BITCOIN: CurrentMarketCoin = {
  coin_id: "bitcoin",
  symbol: "btc",
  name: "Bitcoin",
  image_url: null,
  price_usd: 65160.0,
  price_change_percentage_24h: 1.84,
  market_cap_usd: 1_000_000_000,
  volume_24h_usd: 500_000_000,
  circulating_supply: 19_000_000,
  market_cap_rank: 1,
};

function renderTable(entries: CurrentMarketCoin[] = [BITCOIN]) {
  return render(
    <MemoryRouter>
      <TopMarketCapTable entries={entries} loading={false} error={null} onRetry={vi.fn()} />
    </MemoryRouter>
  );
}

afterEach(() => {
  cleanup();
  navigateMock.mockReset();
});

describe("TopMarketCapTable row navigation", () => {
  it("navigates to Coin Details when clicking the Price cell", () => {
    renderTable();
    fireEvent.click(screen.getByText("$65,160.00"));
    expect(navigateMock).toHaveBeenCalledWith("/coins/btc");
    expect(navigateMock).toHaveBeenCalledTimes(1);
  });

  it("navigates to Coin Details when clicking the Market Cap cell", () => {
    renderTable();
    fireEvent.click(screen.getByText("$1.00B"));
    expect(navigateMock).toHaveBeenCalledWith("/coins/btc");
    expect(navigateMock).toHaveBeenCalledTimes(1);
  });

  it("navigates to Coin Details when clicking the 24H Change cell", () => {
    renderTable();
    fireEvent.click(screen.getByText(/\+1\.84%/));
    expect(navigateMock).toHaveBeenCalledWith("/coins/btc");
    expect(navigateMock).toHaveBeenCalledTimes(1);
  });

  it("navigates when clicking blank row space (the row number cell)", () => {
    renderTable();
    const row = screen.getByRole("link", { name: "Open Bitcoin details" });
    fireEvent.click(row.querySelector("td")!);
    expect(navigateMock).toHaveBeenCalledWith("/coins/btc");
  });

  it("navigates on Enter when the row is focused", () => {
    renderTable();
    const row = screen.getByRole("link", { name: "Open Bitcoin details" });
    fireEvent.keyDown(row, { key: "Enter" });
    expect(navigateMock).toHaveBeenCalledWith("/coins/btc");
    expect(navigateMock).toHaveBeenCalledTimes(1);
  });

  it("navigates on Space when the row is focused", () => {
    renderTable();
    const row = screen.getByRole("link", { name: "Open Bitcoin details" });
    fireEvent.keyDown(row, { key: " " });
    expect(navigateMock).toHaveBeenCalledWith("/coins/btc");
    expect(navigateMock).toHaveBeenCalledTimes(1);
  });

  it("triggers exactly one navigation per activation, even though the row wraps several cells", () => {
    renderTable();
    const row = screen.getByRole("link", { name: "Open Bitcoin details" });
    fireEvent.click(row);
    expect(navigateMock).toHaveBeenCalledTimes(1);
  });

  it("is keyboard-focusable and carries a meaningful accessible label", () => {
    renderTable();
    const row = screen.getByRole("link", { name: "Open Bitcoin details" });
    expect(row).toHaveAttribute("tabIndex", "0");
  });
});
