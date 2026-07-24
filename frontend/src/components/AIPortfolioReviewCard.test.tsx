import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AIPortfolioReviewCard } from "./AIPortfolioReviewCard";
import { ApiError } from "../api/client";
import * as aiApi from "../api/ai";
import type { PortfolioReviewResponse } from "../api/types";

function baseReview(overrides: Partial<PortfolioReviewResponse> = {}): PortfolioReviewResponse {
  return {
    generated_at: "2026-07-24T10:42:00Z",
    provider: "ollama",
    model: "qwen2.5:7b",
    response_time_ms: 1450.2,
    portfolio_summary: {
      total_equity: 105000.0,
      cash_balance: 20000.0,
      invested_value: 80000.0,
      holdings_value: 85000.0,
      realized_profit: 500.0,
      unrealized_profit: 5000.0,
      total_return_percent: 5.0,
      number_of_positions: 2,
    },
    portfolio_health: {
      level: "good",
      diversification_score: 7,
      concentration_risk: "medium",
      cash_allocation_percent: 19.05,
      largest_holding_symbol: "BTC",
      largest_holding_percent: 41.0,
    },
    deterministic_metrics: {
      diversification_score: 7,
      concentration_risk: "medium",
      cash_allocation_percent: 19.05,
      largest_position_symbol: "BTC",
      largest_position_percent: 41.0,
      smallest_position_symbol: "ETH",
      smallest_position_percent: 15.0,
      top_winner_symbol: "BTC",
      top_winner_percent: 12.0,
      top_loser_symbol: "ETH",
      top_loser_percent: -3.0,
      number_of_positions: 2,
    },
    allocation: [
      { label: "BTC", percent: 41.0, value: 43050.0 },
      { label: "ETH", percent: 15.0, value: 15750.0 },
      { label: "CASH", percent: 19.05, value: 20000.0 },
    ],
    top_positions: [
      {
        coin_symbol: "BTC",
        coin_name: "Bitcoin",
        image_url: null,
        allocation_percent: 41.0,
        current_value: 43050.0,
        current_price: 65000.0,
        price_change_percentage_24h: 2.1,
        unrealized_percent: 12.0,
      },
      {
        coin_symbol: "ETH",
        coin_name: "Ethereum",
        image_url: null,
        allocation_percent: 15.0,
        current_value: 15750.0,
        current_price: 3000.0,
        price_change_percentage_24h: -1.4,
        unrealized_percent: -3.0,
      },
    ],
    ai_insights: {
      strengths: ["Spread across two positions plus a meaningful cash buffer."],
      weaknesses: ["BTC makes up over a third of total equity."],
      interesting_observations: ["BTC is the strongest performer at +12.00%."],
      risk_factors: ["Concentration risk is medium."],
      educational_notes: ["Diversification reduces exposure to any single position."],
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
      <AIPortfolioReviewCard />
    </MemoryRouter>
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AIPortfolioReviewCard", () => {
  it('shows "No portfolio review generated." before any click', () => {
    renderCard();

    expect(screen.getByText("No portfolio review generated.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate Review" })).toBeInTheDocument();
  });

  it("shows a loading skeleton and disables the button while the first generation is in flight", async () => {
    const { promise, resolve } = deferred<PortfolioReviewResponse>();
    vi.spyOn(aiApi, "postPortfolioReview").mockReturnValue(promise);

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Review" }));

    const button = await screen.findByRole("button", { name: /Generating review/ });
    expect(button).toBeDisabled();
    expect(screen.getByRole("status", { name: "Generating portfolio review" })).toBeInTheDocument();

    resolve(baseReview());
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());
  });

  it("renders the Portfolio Health cards deterministically", async () => {
    vi.spyOn(aiApi, "postPortfolioReview").mockResolvedValue(baseReview());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Review" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Portfolio Health" })).toBeInTheDocument());
    expect(screen.getByText(/Good/)).toBeInTheDocument();
    expect(screen.getByText("Diversification")).toBeInTheDocument();
    expect(screen.getByText("7/10")).toBeInTheDocument();
    expect(screen.getByText("Concentration")).toBeInTheDocument();
    expect(screen.getByText("Medium")).toBeInTheDocument();
    expect(screen.getByText("Cash Allocation")).toBeInTheDocument();
    expect(screen.getByText("Largest Holding")).toBeInTheDocument();
    expect(screen.getByText("BTC (41.0%)")).toBeInTheDocument();
    expect(screen.getByText("Number of Positions")).toBeInTheDocument();
  });

  it("renders Top Holdings cards for every returned position", async () => {
    vi.spyOn(aiApi, "postPortfolioReview").mockResolvedValue(baseReview());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Review" }));

    await waitFor(() => expect(screen.getByText("Top Holdings")).toBeInTheDocument());
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("ETH")).toBeInTheDocument();
  });

  it("renders all five AI Review sections", async () => {
    vi.spyOn(aiApi, "postPortfolioReview").mockResolvedValue(baseReview());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Review" }));

    await waitFor(() => expect(screen.getByText("Strengths")).toBeInTheDocument());
    expect(screen.getByText("Weaknesses")).toBeInTheDocument();
    expect(screen.getByText("Interesting Observations")).toBeInTheDocument();
    expect(screen.getByText("Risk Factors")).toBeInTheDocument();
    expect(screen.getByText("Educational Notes")).toBeInTheDocument();
    expect(screen.getByText("Spread across two positions plus a meaningful cash buffer.")).toBeInTheDocument();
  });

  it("renders provider/model/generated/generation-time metadata", async () => {
    vi.spyOn(aiApi, "postPortfolioReview").mockResolvedValue(baseReview());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Review" }));

    await waitFor(() => expect(screen.getByText("Provider: ollama")).toBeInTheDocument());
    expect(screen.getByText("Model: qwen2.5:7b")).toBeInTheDocument();
    expect(screen.getByText("Generation time: 1.5s")).toBeInTheDocument();
  });

  it("shows a Refresh button after a successful generation, instead of Generate Review", async () => {
    vi.spyOn(aiApi, "postPortfolioReview").mockResolvedValue(baseReview());

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Review" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Generate Review" })).not.toBeInTheDocument();
  });

  it("shows the real backend error and a retry button when generation fails with no prior review", async () => {
    vi.spyOn(aiApi, "postPortfolioReview").mockRejectedValue(new ApiError("Ollama unavailable", 503));

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Review" }));

    await waitFor(() => expect(screen.getByText("Could not generate a review: Ollama unavailable")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Try Again" })).toBeInTheDocument();
  });

  it("keeps the last successful review visible when a Refresh fails", async () => {
    vi.spyOn(aiApi, "postPortfolioReview")
      .mockResolvedValueOnce(baseReview())
      .mockRejectedValueOnce(new ApiError("Ollama unavailable", 503));

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Review" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    await waitFor(() => expect(screen.getByText(/Could not refresh: Ollama unavailable/)).toBeInTheDocument());
    // the previously-generated review is still on screen, not replaced by a blank error state
    expect(screen.getByRole("heading", { name: "Portfolio Health" })).toBeInTheDocument();
    expect(screen.getByText("Provider: ollama")).toBeInTheDocument();
  });

  it("ignores a second click fired before the first request settles", async () => {
    const { promise, resolve } = deferred<PortfolioReviewResponse>();
    const spy = vi.spyOn(aiApi, "postPortfolioReview").mockReturnValue(promise);

    renderCard();
    const button = screen.getByRole("button", { name: "Generate Review" });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(spy).toHaveBeenCalledTimes(1);

    resolve(baseReview());
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument());
  });

  it("renders an empty (all-cash) portfolio without crashing", async () => {
    vi.spyOn(aiApi, "postPortfolioReview").mockResolvedValue(
      baseReview({
        portfolio_summary: {
          total_equity: 100000.0,
          cash_balance: 100000.0,
          invested_value: 0,
          holdings_value: 0,
          realized_profit: 0,
          unrealized_profit: 0,
          total_return_percent: 0,
          number_of_positions: 0,
        },
        portfolio_health: {
          level: "balanced",
          diversification_score: 0,
          concentration_risk: "unknown",
          cash_allocation_percent: 100,
          largest_holding_symbol: null,
          largest_holding_percent: null,
        },
        allocation: [{ label: "CASH", percent: 100, value: 100000.0 }],
        top_positions: [],
      })
    );

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Review" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Portfolio Health" })).toBeInTheDocument());
    expect(screen.getByText("No holdings yet.")).toBeInTheDocument();
  });

  it("renders a single-holding portfolio's Top Holdings card", async () => {
    vi.spyOn(aiApi, "postPortfolioReview").mockResolvedValue(
      baseReview({
        top_positions: [
          {
            coin_symbol: "BTC",
            coin_name: "Bitcoin",
            image_url: null,
            allocation_percent: 80.0,
            current_value: 84000.0,
            current_price: 65000.0,
            price_change_percentage_24h: 2.1,
            unrealized_percent: 12.0,
          },
        ],
      })
    );

    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Generate Review" }));

    await waitFor(() => expect(screen.getByText("Top Holdings")).toBeInTheDocument());
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.queryByText("ETH")).not.toBeInTheDocument();
  });
});
