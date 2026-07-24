import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WarehouseHealth } from "./WarehouseHealth";
import type { WarehouseHealthResponse } from "../api/types";

const getWarehouseHealthMock = vi.fn();

vi.mock("../api/health", () => ({
  getWarehouseHealth: (...args: unknown[]) => getWarehouseHealthMock(...args),
}));

afterEach(() => {
  cleanup();
  getWarehouseHealthMock.mockReset();
});

function healthyResponse(overrides: Partial<WarehouseHealthResponse> = {}): WarehouseHealthResponse {
  return {
    generated_at: "2026-07-24T16:41:00Z",
    environment: "development",
    overall_status: "healthy",
    database: { status: "healthy", message: "Connected." },
    latest_successful_run: {
      run_id: 72,
      pipeline_name: "coingecko_warehouse_load",
      status: "succeeded",
      started_at: "2026-07-24T16:37:06Z",
      finished_at: "2026-07-24T16:37:06Z",
      error_message: null,
    },
    latest_failed_run: null,
    last_daily_snapshot_date: "2026-07-24",
    last_hourly_snapshot_at: "2026-07-24T15:53:41Z",
    daily_fact_row_count: 1246,
    hourly_fact_row_count: 2696,
    current_coin_count: 103,
    historical_coin_version_count: 0,
    recent_failed_run_count: 0,
    data_quality: { status: "healthy", message: "No failed pipeline runs in the last 7 days." },
    duplicate_check: { status: "healthy", message: "No duplicate fact rows found for either grain." },
    missing_date_coverage: { status: "healthy", message: "No gaps between the last loaded date and today." },
    missing_dates: [],
    stale_coin_check: { status: "healthy", message: "Every tracked coin has a recent daily snapshot." },
    stale_coins: [],
    scheduler: { status: "healthy", message: "Scheduler disabled." },
    scheduler_status: {
      enabled: false,
      running: false,
      interval_minutes: 60,
      currently_running: false,
      last_success_at: null,
      last_failure_at: null,
      next_run_time: null,
    },
    ...overrides,
  };
}

describe("WarehouseHealth", () => {
  it("shows a loading state before data arrives", () => {
    getWarehouseHealthMock.mockReturnValue(new Promise(() => {}));

    render(<WarehouseHealth />);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows an error state with retry when the fetch fails", async () => {
    getWarehouseHealthMock.mockRejectedValue(new Error("Unable to reach the server"));

    render(<WarehouseHealth />);

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText(/unable to reach the server/i)).toBeInTheDocument();
  });

  it("renders every check and the overall healthy status", async () => {
    getWarehouseHealthMock.mockResolvedValue(healthyResponse());

    render(<WarehouseHealth />);

    await waitFor(() => expect(screen.getByText("Warehouse Statistics")).toBeInTheDocument());

    expect(screen.getAllByText("Healthy").length).toBeGreaterThan(0);
    expect(screen.getByText("Database")).toBeInTheDocument();
    expect(screen.getByText("Data Quality (last 7 days)")).toBeInTheDocument();
    expect(screen.getByText(/coingecko_warehouse_load \(run #72\)/)).toBeInTheDocument();
    expect(screen.queryByText(/Missing Dates/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Stale Coins \(/)).not.toBeInTheDocument();
  });

  it("surfaces a duplicate-check error and shows the failed-run error message", async () => {
    getWarehouseHealthMock.mockResolvedValue(
      healthyResponse({
        overall_status: "error",
        duplicate_check: { status: "error", message: "Found 2 duplicate daily fact key(s)." },
        latest_failed_run: {
          run_id: 50,
          pipeline_name: "coingecko_market_snapshot",
          status: "failed",
          started_at: "2026-07-24T00:44:00Z",
          finished_at: "2026-07-24T00:44:01Z",
          error_message: "429 Too Many Requests",
        },
      })
    );

    render(<WarehouseHealth />);

    await waitFor(() => expect(screen.getByText(/Found 2 duplicate/)).toBeInTheDocument());
    expect(screen.getByText(/429 Too Many Requests/)).toBeInTheDocument();
  });

  it("lists missing dates and stale coins when present", async () => {
    getWarehouseHealthMock.mockResolvedValue(
      healthyResponse({
        missing_date_coverage: { status: "warning", message: "2 day(s) missing." },
        missing_dates: ["2026-07-22", "2026-07-23"],
        stale_coin_check: { status: "warning", message: "1 tracked coin(s) stale." },
        stale_coins: [{ coin_id: "dogecoin", symbol: "DOGE", last_seen_date: "2026-07-10" }],
      })
    );

    render(<WarehouseHealth />);

    await waitFor(() => expect(screen.getByText(/Missing Dates \(2\)/)).toBeInTheDocument());
    expect(screen.getByText(/Stale Coins \(1\)/)).toBeInTheDocument();
    expect(screen.getByText("DOGE")).toBeInTheDocument();
  });
});
