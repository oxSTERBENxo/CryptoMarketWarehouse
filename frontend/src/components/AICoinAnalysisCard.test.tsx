import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AICoinAnalysisCard } from "./AICoinAnalysisCard";
import { ApiError } from "../api/client";
import * as aiApi from "../api/ai";
import type { CoinAnalysisResponse } from "../api/types";

function baseAnalysis(overrides: Partial<CoinAnalysisResponse> = {}): CoinAnalysisResponse {
  return {
    generated_at: "2026-07-24T10:42:00Z",
    provider: "ollama",
    model: "qwen2.5:7b",
    response_time_ms: 3200,
    coin_information: {
      coin_id: "bitcoin",
      symbol: "BTC",
      name: "Bitcoin",
      image_url: null,
      price: 65000.0,
      change_24h: 2.5,
      market_cap: 1_300_000_000_000.0,
      market_cap_rank: 1,
      volume_24h: 29_000_000_000.0,
      circulating_supply: 19_000_000.0,
      history_observation_count: 30,
      history_start_date: "2026-06-24",
      history_end_date: "2026-07-24",
    },
    deterministic_metrics: {
      price_trend: "bullish",
      trend_percent_change: 8.33,
      momentum_24h_percent: 2.5,
      volatility_level: "medium",
      volatility_percent: 12.0,
      liquidity_level: "high",
      liquidity_ratio_percent: 2.2,
      market_cap_tier: "large_cap",
      volume_trend: "stable",
      average_daily_movement_percent: 3.1,
      period_high: 66000.0,
      period_low: 58000.0,
      distance_from_high_percent: -1.5,
      distance_from_low_percent: 12.1,
    },
    ai_insights: {
      overview: ["Bitcoin is trending upward over the tracked period."],
      performance: ["24h change is +2.50%, in line with recent momentum."],
      market_position: ["Ranked #1 by market capitalization (large cap)."],
      things_to_watch: ["Volume is stable relative to its own average."],
      risk: ["This is educational market analytics, not financial advice."],
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

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AICoinAnalysisCard", () => {
  it('shows "No analysis generated." before any click', () => {
    render(<AICoinAnalysisCard symbol="btc" />);

    expect(screen.getByText("No analysis generated.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate Analysis" })).toBeInTheDocument();
  });

  it("shows a loading skeleton and disables the button while the first generation is in flight", async () => {
    const { promise, resolve } = deferred<CoinAnalysisResponse>();
    vi.spyOn(aiApi, "postCoinAnalysis").mockReturnValue(promise);

    render(<AICoinAnalysisCard symbol="btc" />);
    fireEvent.click(screen.getByRole("button", { name: "Generate Analysis" }));

    const button = await screen.findByRole("button", { name: /Generating analysis/ });
    expect(button).toBeDisabled();
    expect(screen.getByRole("status", { name: "Generating coin analysis" })).toBeInTheDocument();

    resolve(baseAnalysis());
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());
  });

  it("calls postCoinAnalysis with the given coin symbol", async () => {
    const spy = vi.spyOn(aiApi, "postCoinAnalysis").mockResolvedValue(baseAnalysis());

    render(<AICoinAnalysisCard symbol="btc" />);
    fireEvent.click(screen.getByRole("button", { name: "Generate Analysis" }));

    await waitFor(() => expect(spy).toHaveBeenCalledWith("btc"));
  });

  it("renders the Coin Health status cards deterministically", async () => {
    vi.spyOn(aiApi, "postCoinAnalysis").mockResolvedValue(baseAnalysis());

    render(<AICoinAnalysisCard symbol="btc" />);
    fireEvent.click(screen.getByRole("button", { name: "Generate Analysis" }));

    await waitFor(() => expect(screen.getByText("Coin Health")).toBeInTheDocument());
    expect(screen.getByText("Price Trend")).toBeInTheDocument();
    expect(screen.getByText("Bullish")).toBeInTheDocument();
    expect(screen.getByText("Volatility")).toBeInTheDocument();
    expect(screen.getByText("Medium")).toBeInTheDocument();
    expect(screen.getByText("Liquidity")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("Market Tier")).toBeInTheDocument();
    expect(screen.getByText("Large Cap")).toBeInTheDocument();
  });

  it("renders all five AI interpretation sections", async () => {
    vi.spyOn(aiApi, "postCoinAnalysis").mockResolvedValue(baseAnalysis());

    render(<AICoinAnalysisCard symbol="btc" />);
    fireEvent.click(screen.getByRole("button", { name: "Generate Analysis" }));

    await waitFor(() => expect(screen.getByText("AI Interpretation")).toBeInTheDocument());
    expect(screen.getByText("Today's Performance")).toBeInTheDocument();
    expect(screen.getByText("Market Position")).toBeInTheDocument();
    expect(screen.getByText("Things Worth Watching")).toBeInTheDocument();
    expect(screen.getByText("Risk Factors")).toBeInTheDocument();
    expect(screen.getByText("Bitcoin is trending upward over the tracked period.")).toBeInTheDocument();
  });

  it("renders provider/model/generated/generation-time metadata", async () => {
    vi.spyOn(aiApi, "postCoinAnalysis").mockResolvedValue(baseAnalysis());

    render(<AICoinAnalysisCard symbol="btc" />);
    fireEvent.click(screen.getByRole("button", { name: "Generate Analysis" }));

    await waitFor(() => expect(screen.getByText("Provider: ollama")).toBeInTheDocument());
    expect(screen.getByText("Model: qwen2.5:7b")).toBeInTheDocument();
    expect(screen.getByText("Generation time: 3.2s")).toBeInTheDocument();
  });

  it("shows a Refresh button after a successful generation, instead of Generate Analysis", async () => {
    vi.spyOn(aiApi, "postCoinAnalysis").mockResolvedValue(baseAnalysis());

    render(<AICoinAnalysisCard symbol="btc" />);
    fireEvent.click(screen.getByRole("button", { name: "Generate Analysis" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Generate Analysis" })).not.toBeInTheDocument();
  });

  it("shows the real backend error and a retry button when generation fails with no prior analysis", async () => {
    vi.spyOn(aiApi, "postCoinAnalysis").mockRejectedValue(new ApiError("Unknown coin symbol: 'ZZZ'", 404));

    render(<AICoinAnalysisCard symbol="zzz" />);
    fireEvent.click(screen.getByRole("button", { name: "Generate Analysis" }));

    await waitFor(() =>
      expect(screen.getByText("Could not generate an analysis: Unknown coin symbol: 'ZZZ'")).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: "Try Again" })).toBeInTheDocument();
  });

  it("keeps the last successful analysis visible when a Refresh fails", async () => {
    vi.spyOn(aiApi, "postCoinAnalysis")
      .mockResolvedValueOnce(baseAnalysis())
      .mockRejectedValueOnce(new ApiError("Ollama unavailable", 503));

    render(<AICoinAnalysisCard symbol="btc" />);
    fireEvent.click(screen.getByRole("button", { name: "Generate Analysis" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    await waitFor(() => expect(screen.getByText(/Could not refresh: Ollama unavailable/)).toBeInTheDocument());
    // the previously-generated analysis is still on screen, not replaced by a blank error state
    expect(screen.getByText("Coin Health")).toBeInTheDocument();
    expect(screen.getByText("Provider: ollama")).toBeInTheDocument();
  });

  it("ignores a second click fired before the first request settles", async () => {
    const { promise, resolve } = deferred<CoinAnalysisResponse>();
    const spy = vi.spyOn(aiApi, "postCoinAnalysis").mockReturnValue(promise);

    render(<AICoinAnalysisCard symbol="btc" />);
    const button = screen.getByRole("button", { name: "Generate Analysis" });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(spy).toHaveBeenCalledTimes(1);

    resolve(baseAnalysis());
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());
  });

  it("resets to the idle state when the coin symbol changes, never showing the previous coin's analysis", async () => {
    vi.spyOn(aiApi, "postCoinAnalysis").mockResolvedValue(baseAnalysis());

    const { rerender } = render(<AICoinAnalysisCard symbol="btc" />);
    fireEvent.click(screen.getByRole("button", { name: "Generate Analysis" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());

    rerender(<AICoinAnalysisCard symbol="eth" />);

    expect(screen.getByText("No analysis generated.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate Analysis" })).toBeInTheDocument();
    expect(screen.queryByText("Coin Health")).not.toBeInTheDocument();
  });

  it("generates a fresh analysis for the newly switched-to coin", async () => {
    const spy = vi.spyOn(aiApi, "postCoinAnalysis").mockResolvedValue(baseAnalysis());

    const { rerender } = render(<AICoinAnalysisCard symbol="btc" />);
    rerender(<AICoinAnalysisCard symbol="eth" />);
    fireEvent.click(screen.getByRole("button", { name: "Generate Analysis" }));

    await waitFor(() => expect(spy).toHaveBeenCalledWith("eth"));
  });
});
