import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RecoveryStatusBanner } from "./RecoveryStatusBanner";
import * as adminApi from "../api/admin";
import type { DataRecoveryStatus } from "../api/admin";

function status(overrides: Partial<DataRecoveryStatus> = {}): DataRecoveryStatus {
  return {
    status: "idle",
    last_daily_snapshot_date: null,
    expected_latest_daily_date: null,
    missing_dates: [],
    dates_completed: [],
    current_date_processing: null,
    started_at: null,
    completed_at: null,
    errors: [],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("RecoveryStatusBanner", () => {
  it("shows progress while a recovery run is active", async () => {
    vi.spyOn(adminApi, "getDataRecoveryStatus").mockResolvedValue(
      status({
        status: "running",
        missing_dates: ["2026-07-20", "2026-07-21", "2026-07-22", "2026-07-23"],
        dates_completed: ["2026-07-20", "2026-07-21"],
      })
    );

    render(<RecoveryStatusBanner />);

    await waitFor(() =>
      expect(screen.getByText("Restoring 4 missing daily snapshots: 2 of 4 complete")).toBeInTheDocument()
    );
  });

  it("renders nothing when idle with nothing to recover", async () => {
    vi.spyOn(adminApi, "getDataRecoveryStatus").mockResolvedValue(status({ status: "idle" }));

    const { container } = render(<RecoveryStatusBanner />);

    await waitFor(() => expect(adminApi.getDataRecoveryStatus).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when completed with zero missing dates (no permanent success banner)", async () => {
    vi.spyOn(adminApi, "getDataRecoveryStatus").mockResolvedValue(
      status({ status: "completed", missing_dates: [] })
    );

    const { container } = render(<RecoveryStatusBanner />);

    await waitFor(() => expect(adminApi.getDataRecoveryStatus).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the up-to-date message once a run with real gaps completes", async () => {
    vi.spyOn(adminApi, "getDataRecoveryStatus").mockResolvedValue(
      status({ status: "completed", missing_dates: ["2026-07-23"], dates_completed: ["2026-07-23"] })
    );

    render(<RecoveryStatusBanner />);

    await waitFor(() => expect(screen.getByText("Historical market data is up to date.")).toBeInTheDocument());
  });
});
