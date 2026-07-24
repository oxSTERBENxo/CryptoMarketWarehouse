import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AIMarketSummaryCard } from "./AIMarketSummaryCard";
import { ApiError } from "../api/client";
import * as aiApi from "../api/ai";
import type { AttentionCoin, MarketCoinEntry, MarketSummaryResponse } from "../api/types";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

function coin(overrides: Partial<MarketCoinEntry> = {}): MarketCoinEntry {
  return {
    coin_id: "bitcoin",
    name: "Bitcoin",
    symbol: "btc",
    image_url: null,
    price: 65000.0,
    change_24h: 2.5,
    volume_24h: 25_000_000_000.0,
    market_cap: 1_300_000_000_000.0,
    market_cap_rank: 1,
    volume_share_percent: 26.4,
    ...overrides,
  };
}

function attentionCoin(overrides: Partial<AttentionCoin> = {}): AttentionCoin {
  return {
    ...coin(),
    category: "positive_momentum",
    reason: "Positive 24h price movement (+9.90%) with above-median trading volume.",
    ...overrides,
  };
}

function baseSummary(overrides: Partial<MarketSummaryResponse> = {}): MarketSummaryResponse {
  return {
    generated_at: "2026-07-24T10:42:00Z",
    provider: "ollama",
    model: "qwen2.5:7b",
    response_time_ms: 2500,
    market_status: {
      direction: "mixed",
      headline:
        "Market conditions are mixed, with 16 of 100 tracked assets advancing and 63 declining, and an " +
        "average 24-hour change of +2.58%.",
      average_change_24h: 2.58,
      gainers_count: 16,
      losers_count: 63,
      unchanged_count: 21,
      coins_tracked: 100,
      snapshot_time: "2026-07-24T10:00:00Z",
    },
    metrics: { total_market_cap: 2_255_941_544_333.0, total_volume_24h: 94_859_076_454.78 },
    attention_coins: [attentionCoin()],
    top_gainers: [coin({ coin_id: "solana", name: "Solana", symbol: "sol", change_24h: 9.9 })],
    top_losers: [coin({ coin_id: "cardano", name: "Cardano", symbol: "ada", change_24h: -8.0 })],
    most_active: [coin({ coin_id: "tether", name: "Tether", symbol: "usdt", volume_24h: 40_000_000_000.0 })],
    ai_insights: {
      market_overview: ["Breadth is weak despite a positive average change."],
      what_stands_out: ["Tether leads 24h trading volume."],
      risk_and_caution: ["This is educational analytics, not financial advice."],
    },
    ...overrides,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function renderCard() {
  return render(
    <MemoryRouter>
      <AIMarketSummaryCard />
    </MemoryRouter>
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  navigateMock.mockReset();
});

describe("AIMarketSummaryCard", () => {
  it('shows "No summary generated." before any click', () => {
    renderCard();
    expect(screen.getByText("No summary generated.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate Summary" })).toBeInTheDocument();
  });

  it("shows a loading skeleton and disables the button while the first generation is in flight", async () => {
    const { promise, resolve } = deferred<MarketSummaryResponse>();
    vi.spyOn(aiApi, "postMarketSummary").mockReturnValue(promise);

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    const button = await screen.findByRole("button", { name: /Generating summary/ });
    expect(button).toBeDisabled();
    expect(screen.getByRole("status", { name: "Generating market summary" })).toBeInTheDocument();

    resolve(baseSummary());
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());
  });

  it("renders the market status header deterministically, not as Markdown", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() => expect(screen.getByText("Mixed")).toBeInTheDocument());
    expect(screen.getByText(/Market conditions are mixed/)).toBeInTheDocument();
    // several of these numbers appear twice: once as a stat chip, once inside a metric card
    expect(screen.getAllByText("+2.58%").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("16").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("63").length).toBeGreaterThanOrEqual(1);
  });

  it("renders the 4 metric cards", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() => expect(screen.getByText("Total Market Capitalization")).toBeInTheDocument());
    expect(screen.getByText("Total 24h Trading Volume")).toBeInTheDocument();
    expect(screen.getByText("Average 24h Change")).toBeInTheDocument();
    expect(screen.getByText("Gainers vs Losers")).toBeInTheDocument();
    expect(screen.getByText("$2.26T")).toBeInTheDocument();
  });

  it("renders attention coins grouped by category with a disclaimer, not a recommendation", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() => expect(screen.getByText("Coins Attracting Attention")).toBeInTheDocument());
    expect(screen.getByText("Strongest Positive Momentum")).toBeInTheDocument();
    expect(screen.getByText(/above-median trading volume/)).toBeInTheDocument();
    expect(
      screen.getByText("Attention indicators describe current market activity and are not buying recommendations.")
    ).toBeInTheDocument();
  });

  it("renders top gainers and losers side by side, not as a Markdown list", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() => expect(screen.getByText("Top Gainers")).toBeInTheDocument());
    expect(screen.getByText("Top Losers")).toBeInTheDocument();
    expect(screen.getByText("Solana")).toBeInTheDocument();
    expect(screen.getByText("Cardano")).toBeInTheDocument();
  });

  it("renders trading activity with each coin's share of tracked volume", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() => expect(screen.getByText("Trading Activity")).toBeInTheDocument());
    expect(screen.getByText("Tether")).toBeInTheDocument();
    expect(screen.getByText("26.4% of tracked 24h volume")).toBeInTheDocument();
  });

  it("renders the three AI Insights sections, each interpreting rather than repeating tables", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() => expect(screen.getByText("AI Insights")).toBeInTheDocument());
    expect(screen.getByText("Market Overview")).toBeInTheDocument();
    expect(screen.getByText("What Stands Out")).toBeInTheDocument();
    expect(screen.getByText("Risk and Caution")).toBeInTheDocument();
    expect(screen.getByText("Breadth is weak despite a positive average change.")).toBeInTheDocument();
  });

  it("renders provider/model/generated/generation-time metadata", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() => expect(screen.getByText("Provider: ollama")).toBeInTheDocument());
    expect(screen.getByText("Model: qwen2.5:7b")).toBeInTheDocument();
    expect(screen.getByText("Generation time: 2.5s")).toBeInTheDocument();
  });

  it("navigates to Coin Details when an attention coin row is clicked", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));
    await waitFor(() => expect(screen.getByText("Coins Attracting Attention")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("link", { name: "Open Bitcoin details" }));

    expect(navigateMock).toHaveBeenCalledWith("/coins/btc");
  });

  it("navigates to Coin Details when a top-mover row is clicked", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));
    await waitFor(() => expect(screen.getByText("Solana")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("link", { name: "Open Solana details" }));

    expect(navigateMock).toHaveBeenCalledWith("/coins/sol");
  });

  it("shows a Refresh button after a successful generation, instead of Generate Summary", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Generate Summary" })).not.toBeInTheDocument();
  });

  it("shows the real backend error and a retry button when generation fails with no prior summary", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockRejectedValue(
      new ApiError("No market data has been ingested yet.", 404)
    );

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() =>
      expect(
        screen.getByText("Could not generate a summary: No market data has been ingested yet.")
      ).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: "Try Again" })).toBeInTheDocument();
  });

  it("keeps the last successful summary visible when a Refresh fails", async () => {
    vi.spyOn(aiApi, "postMarketSummary")
      .mockResolvedValueOnce(baseSummary())
      .mockRejectedValueOnce(new ApiError("Ollama unavailable", 503));

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    await waitFor(() => expect(screen.getByText(/Could not refresh: Ollama unavailable/)).toBeInTheDocument());
    // the previously-generated summary is still on screen, not replaced by a blank error state
    expect(screen.getByText("Coins Attracting Attention")).toBeInTheDocument();
    expect(screen.getByText("Provider: ollama")).toBeInTheDocument();
  });

  it("ignores a second click fired before the first request settles", async () => {
    const { promise, resolve } = deferred<MarketSummaryResponse>();
    const spy = vi.spyOn(aiApi, "postMarketSummary").mockReturnValue(promise);

    renderCard();
    const button = screen.getByRole("button", { name: "Generate Summary" });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(spy).toHaveBeenCalledTimes(1);

    resolve(baseSummary());
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());
  });

  it("renders a fallback message when no coins currently attract attention", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(baseSummary({ attention_coins: [] }));

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() =>
      expect(screen.getByText("No coins currently stand out by these measures.")).toBeInTheDocument()
    );
  });

  it("renders a fallback message when there are no gainers or losers", async () => {
    vi.spyOn(aiApi, "postMarketSummary").mockResolvedValue(
      baseSummary({ top_gainers: [], top_losers: [] })
    );

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Summary" }));

    await waitFor(() => expect(screen.getByText("No gainers in this snapshot.")).toBeInTheDocument());
    expect(screen.getByText("No losers in this snapshot.")).toBeInTheDocument();
  });
});
