import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnalyticsExplorer } from "./AnalyticsExplorer";
import type { ExplorerResponse, ExplorerResultRow } from "../api/types";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

const runExplorerQueryMock = vi.fn();
const exportExplorerCsvMock = vi.fn();

vi.mock("../api/explorer", () => ({
  runExplorerQuery: (...args: unknown[]) => runExplorerQueryMock(...args),
  exportExplorerCsv: (...args: unknown[]) => exportExplorerCsvMock(...args),
}));

function row(symbol: string, overrides: Partial<ExplorerResultRow> = {}): ExplorerResultRow {
  return {
    coin_id: symbol.toLowerCase(),
    symbol,
    name: symbol === "BTC" ? "Bitcoin" : symbol,
    image_url: null,
    start_date: "2026-06-01",
    end_date: "2026-06-30",
    start_price: 100,
    end_price: 110,
    dollar_change: 10,
    percent_change: 10,
    low_price: 95,
    high_price: 115,
    avg_price: 105,
    avg_volume: 1_000_000,
    volatility_percent: 21.05,
    start_rank: 10,
    end_rank: 8,
    rank_change: 2,
    market_cap_usd: 50_000_000,
    observation_count: 30,
    ...overrides,
  };
}

function response(rows: ExplorerResultRow[], overrides: Partial<ExplorerResponse> = {}): ExplorerResponse {
  return {
    analysis_label: "Price increased by at least X%",
    metric: "price",
    condition: "increased_by_percent",
    from_date: "2026-06-01",
    to_date: "2026-06-30",
    threshold: 5,
    sort_by: "percent_change",
    sort_order: "desc",
    total_results: rows.length,
    offset: 0,
    limit: 25,
    summary: {
      results_found: rows.length,
      average_percent_change: 10,
      largest_increase_percent: 10,
      largest_increase_symbol: rows[0]?.symbol ?? null,
      largest_decrease_percent: 10,
      largest_decrease_symbol: rows[rows.length - 1]?.symbol ?? null,
      average_volume: 1_000_000,
    },
    rows,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AnalyticsExplorer />
    </MemoryRouter>
  );
}

function runAnalysis() {
  fireEvent.click(screen.getByRole("button", { name: "Run Analysis" }));
}

beforeEach(() => {
  runExplorerQueryMock.mockResolvedValue(response([row("BTC")]));
  // Each test must start with a clean slate -- the page persists form/request state to
  // sessionStorage and Recent Queries to localStorage (both real browser APIs jsdom shares across
  // tests in this file), so a previous test's leftover state would otherwise leak into the next.
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  navigateMock.mockReset();
  runExplorerQueryMock.mockReset();
  exportExplorerCsvMock.mockReset();
  sessionStorage.clear();
  localStorage.clear();
});

describe("AnalyticsExplorer", () => {
  it("shows the configure hint and no results before the first run", () => {
    renderPage();
    expect(screen.getByText(/Configure an analysis above/)).toBeTruthy();
    expect(runExplorerQueryMock).not.toHaveBeenCalled();
  });

  it("runs the analysis and renders the result table with summary cards", async () => {
    renderPage();
    runAnalysis();

    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeTruthy());
    expect(runExplorerQueryMock).toHaveBeenCalledTimes(1);
    expect(runExplorerQueryMock).toHaveBeenCalledWith(
      expect.objectContaining({
        metric: "price",
        condition: "increased_by_percent",
        threshold: 5,
        sort_by: null,
        offset: 0,
      })
    );
    expect(screen.getByText("Results Found")).toBeTruthy();
    expect(screen.getByText("Average Change")).toBeTruthy();
    expect(screen.getByText(/Showing 1–1 of 1 results/)).toBeTruthy();
  });

  it("shows a loading state while the analysis runs", async () => {
    let resolve!: (value: ExplorerResponse) => void;
    runExplorerQueryMock.mockReturnValue(new Promise((r) => (resolve = r)));
    renderPage();
    runAnalysis();

    expect(screen.getByText("Running analysis...")).toBeTruthy();
    resolve(response([row("BTC")]));
    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeTruthy());
  });

  it("shows the empty state when the analysis matches nothing", async () => {
    runExplorerQueryMock.mockResolvedValue(response([]));
    renderPage();
    runAnalysis();

    await waitFor(() => expect(screen.getByText(/No coins matched this analysis/)).toBeTruthy());
  });

  it("rejects an inverted date range without calling the API", () => {
    renderPage();
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-07-01" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-06-01" } });
    runAnalysis();

    expect(screen.getByRole("alert").textContent).toMatch(/From date must not be later/);
    expect(runExplorerQueryMock).not.toHaveBeenCalled();
  });

  it("requires a threshold for threshold-based analyses", () => {
    renderPage();
    fireEvent.change(screen.getByLabelText("Minimum increase (%)"), { target: { value: "" } });
    runAnalysis();

    expect(screen.getByRole("alert").textContent).toMatch(/required for this analysis/);
    expect(runExplorerQueryMock).not.toHaveBeenCalled();
  });

  it("offers only the analyses valid for the selected metric", () => {
    renderPage();
    fireEvent.change(screen.getByLabelText("Metric"), { target: { value: "volatility" } });

    const analysisSelect = screen.getByLabelText("Analysis Type") as HTMLSelectElement;
    const labels = Array.from(analysisSelect.options).map((option) => option.text);
    expect(labels).toEqual(["Most volatile", "Least volatile"]);
  });

  it("sends the optional filters with the request", async () => {
    renderPage();
    fireEvent.click(screen.getByText("Optional filters"));
    fireEvent.change(screen.getByLabelText("Min market cap ($)"), { target: { value: "1000000" } });
    fireEvent.change(screen.getByLabelText("Worst rank (max)"), { target: { value: "20" } });
    runAnalysis();

    await waitFor(() => expect(runExplorerQueryMock).toHaveBeenCalled());
    expect(runExplorerQueryMock).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.objectContaining({ min_market_cap: 1_000_000, max_rank: 20 }),
      })
    );
  });

  it("navigates to Coin Details with the analyzed date range on row click", async () => {
    renderPage();
    runAnalysis();

    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeTruthy());
    fireEvent.click(screen.getByRole("link", { name: /Open Bitcoin details/ }));
    expect(navigateMock).toHaveBeenCalledWith("/coins/btc?from=2026-06-01&to=2026-06-30");
  });

  it("re-queries with the clicked column as the sort field", async () => {
    renderPage();
    runAnalysis();

    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Market Cap/ }));

    await waitFor(() => expect(runExplorerQueryMock).toHaveBeenCalledTimes(2));
    expect(runExplorerQueryMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort_by: "market_cap", offset: 0 })
    );
  });

  it("applies a date preset to the From/To fields", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "90D" }));

    const fromInput = screen.getByLabelText("From") as HTMLInputElement;
    const toInput = screen.getByLabelText("To") as HTMLInputElement;
    const expectedFrom = new Date();
    expectedFrom.setDate(expectedFrom.getDate() - 90);

    expect(toInput.value).toBe(new Date().toISOString().slice(0, 10));
    expect(fromInput.value).toBe(expectedFrom.toISOString().slice(0, 10));
  });

  it("resets the form and clears results with Reset filters", async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText("Metric"), { target: { value: "volatility" } });
    runAnalysis();
    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));

    expect((screen.getByLabelText("Metric") as HTMLSelectElement).value).toBe("price");
    expect(screen.getByText(/Configure an analysis above/)).toBeTruthy();
  });

  it("saves a run as a Recent Query and re-runs it on click", async () => {
    renderPage();
    runAnalysis();
    await waitFor(() => expect(runExplorerQueryMock).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));
    expect(screen.getByText(/Configure an analysis above/)).toBeTruthy();

    // The Recent Query chip survives Reset (it's a persistent history entry, not part of the
    // form being reset) and re-running it restores both the form and the results.
    fireEvent.click(screen.getByRole("button", { name: /Increased by at least X%/ }));

    await waitFor(() => expect(runExplorerQueryMock).toHaveBeenCalledTimes(2));
    expect((screen.getByLabelText("Metric") as HTMLSelectElement).value).toBe("price");
  });

  it("restores the last submitted query after remounting (simulating browser Back from Coin Details)", async () => {
    const { unmount } = renderPage();
    fireEvent.change(screen.getByLabelText("Metric"), { target: { value: "volume" } });
    runAnalysis();
    await waitFor(() => expect(runExplorerQueryMock).toHaveBeenCalledTimes(1));
    unmount();

    renderPage();

    await waitFor(() => expect(runExplorerQueryMock).toHaveBeenCalledTimes(2));
    expect((screen.getByLabelText("Metric") as HTMLSelectElement).value).toBe("volume");
    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeTruthy());
  });

  it("exports the current analysis as CSV", async () => {
    exportExplorerCsvMock.mockResolvedValue({ csv: "Symbol\nBTC", filename: "analytics-explorer.csv" });
    const createObjectURL = vi.fn(() => "blob:mock");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, configurable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: revokeObjectURL, configurable: true });

    renderPage();
    runAnalysis();
    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    await waitFor(() => expect(exportExplorerCsvMock).toHaveBeenCalledTimes(1));
    expect(createObjectURL).toHaveBeenCalledTimes(1);
  });
});
