import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TakeSnapshotButton } from "./TakeSnapshotButton";
import { ApiError } from "../api/client";
import * as adminApi from "../api/admin";
import type { RefreshMarketDataResult } from "../api/admin";

function baseResult(overrides: Partial<RefreshMarketDataResult> = {}): RefreshMarketDataResult {
  return {
    status: "succeeded",
    coins_fetched: 100,
    staging_rows_inserted: 100,
    daily_snapshots_inserted: 0,
    intraday_snapshots_inserted: 1,
    coins_updated: 0,
    missing_dates_found: 0,
    dates_backfilled: 0,
    dates_skipped: 0,
    elapsed_seconds: 1.5,
    refreshed_at: "2026-07-24T10:42:00Z",
    intraday_snapshots_today: 1,
    errors: [],
    ...overrides,
  };
}

/** Resolves/rejects on demand so tests can inspect the loading/disabled state mid-request. */
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

describe("TakeSnapshotButton", () => {
  it("shows the last-refreshed status line before any click", () => {
    render(
      <TakeSnapshotButton
        onRefreshed={vi.fn()}
        lastRefreshedAt="2026-07-24T10:42:00Z"
        latestDailySnapshotDate={null}
      />
    );
    expect(screen.getByText(/Last refreshed: Jul 24, 2026/)).toBeInTheDocument();
  });

  it("shows the latest daily snapshot date when provided", () => {
    render(
      <TakeSnapshotButton onRefreshed={vi.fn()} lastRefreshedAt={null} latestDailySnapshotDate="2026-07-24" />
    );
    expect(screen.getByText(/Latest daily snapshot: Jul 24, 2026/)).toBeInTheDocument();
  });

  it("disables the button and shows the loading label immediately while the request is in flight", async () => {
    const { promise, resolve } = deferred<RefreshMarketDataResult>();
    vi.spyOn(adminApi, "refreshMarketData").mockReturnValue(promise);

    render(<TakeSnapshotButton onRefreshed={vi.fn()} lastRefreshedAt={null} latestDailySnapshotDate={null} />);
    fireEvent.click(screen.getByRole("button"));

    const button = await screen.findByRole("button", { name: /Fetching latest market data/ });
    expect(button).toBeDisabled();

    await act(async () => {
      resolve(baseResult());
      await promise;
    });
  });

  it('shows "New daily and intraday snapshots added successfully." when both landed', async () => {
    vi.spyOn(adminApi, "refreshMarketData").mockResolvedValue(
      baseResult({ daily_snapshots_inserted: 5, intraday_snapshots_inserted: 1 })
    );
    const onRefreshed = vi.fn();

    render(<TakeSnapshotButton onRefreshed={onRefreshed} lastRefreshedAt={null} latestDailySnapshotDate={null} />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() =>
      expect(screen.getByText("New daily and intraday snapshots added successfully.")).toBeInTheDocument()
    );
    expect(onRefreshed).toHaveBeenCalledTimes(1);
  });

  it('shows "intraday snapshot added; daily already existed" on a same-day repeat press', async () => {
    vi.spyOn(adminApi, "refreshMarketData").mockResolvedValue(
      baseResult({ daily_snapshots_inserted: 0, intraday_snapshots_inserted: 1, intraday_snapshots_today: 3 })
    );
    const onRefreshed = vi.fn();

    render(<TakeSnapshotButton onRefreshed={onRefreshed} lastRefreshedAt={null} latestDailySnapshotDate={null} />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() =>
      expect(
        screen.getByText("New intraday snapshot added; today's daily snapshot already existed.")
      ).toBeInTheDocument()
    );
    expect(screen.getByText("Intraday snapshots today: 3")).toBeInTheDocument();
    expect(onRefreshed).toHaveBeenCalledTimes(1);
  });

  it("increments the displayed intraday count on a second successful press", async () => {
    const spy = vi
      .spyOn(adminApi, "refreshMarketData")
      .mockResolvedValueOnce(baseResult({ intraday_snapshots_today: 1 }))
      .mockResolvedValueOnce(baseResult({ intraday_snapshots_today: 2 }));

    render(<TakeSnapshotButton onRefreshed={vi.fn()} lastRefreshedAt={null} latestDailySnapshotDate={null} />);
    const button = screen.getByRole("button");

    fireEvent.click(button);
    await waitFor(() => expect(screen.getByText("Intraday snapshots today: 1")).toBeInTheDocument());

    fireEvent.click(button);
    await waitFor(() => expect(screen.getByText("Intraday snapshots today: 2")).toBeInTheDocument());
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it('shows "partial errors" when the backend reports errors alongside a succeeded status', async () => {
    vi.spyOn(adminApi, "refreshMarketData").mockResolvedValue(
      baseResult({ daily_snapshots_inserted: 3, errors: ["one coin failed to price"] })
    );
    const onRefreshed = vi.fn();

    render(<TakeSnapshotButton onRefreshed={onRefreshed} lastRefreshedAt={null} latestDailySnapshotDate={null} />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(screen.getByText("Snapshot completed with partial errors.")).toBeInTheDocument());
    expect(onRefreshed).toHaveBeenCalledTimes(1);
  });

  it("shows the real backend error and does not call onRefreshed when the pipeline fails", async () => {
    vi.spyOn(adminApi, "refreshMarketData").mockResolvedValue(
      baseResult({ status: "failed", coins_fetched: 0, staging_rows_inserted: 0, errors: ["CoinGecko unreachable"] })
    );
    const onRefreshed = vi.fn();

    render(<TakeSnapshotButton onRefreshed={onRefreshed} lastRefreshedAt={null} latestDailySnapshotDate={null} />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() =>
      expect(screen.getByText("Snapshot failed: CoinGecko unreachable")).toBeInTheDocument()
    );
    expect(onRefreshed).not.toHaveBeenCalled();
  });

  it("shows the real backend error on a network/HTTP failure (e.g. 409 already running)", async () => {
    vi.spyOn(adminApi, "refreshMarketData").mockRejectedValue(
      new ApiError("A pipeline run is already in progress", 409)
    );
    const onRefreshed = vi.fn();

    render(<TakeSnapshotButton onRefreshed={onRefreshed} lastRefreshedAt={null} latestDailySnapshotDate={null} />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() =>
      expect(screen.getByText("Snapshot failed: A pipeline run is already in progress")).toBeInTheDocument()
    );
    expect(onRefreshed).not.toHaveBeenCalled();
  });

  it("ignores a second/third click fired before the first request settles (exactly one active request)", async () => {
    const { promise, resolve } = deferred<RefreshMarketDataResult>();
    const spy = vi.spyOn(adminApi, "refreshMarketData").mockReturnValue(promise);

    render(<TakeSnapshotButton onRefreshed={vi.fn()} lastRefreshedAt={null} latestDailySnapshotDate={null} />);
    const button = screen.getByRole("button");
    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.click(button);

    expect(spy).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolve(baseResult());
      await promise;
    });
  });
});
