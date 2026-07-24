import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { refreshMarketData } from "../api/admin";
import type { RefreshMarketDataResult } from "../api/admin";
import { ApiError } from "../api/client";
import { formatDate, formatDateTime } from "../utils/format";
import "./TakeSnapshotButton.css";

interface TakeSnapshotButtonProps {
  /** Called after any non-failed refresh completes, so the dashboard can refetch current values. */
  onRefreshed: () => void;
  /** Timestamp of the most recently ingested data (from GET /analytics/current-market), shown as
   * the "Last refreshed" status line -- correct even before the button has ever been pressed. */
  lastRefreshedAt: string | null | undefined;
  /** Most recent daily warehouse snapshot date (from GET /analytics/overview), for the optional
   * "Latest daily snapshot: ..." status line (Part 12). */
  latestDailySnapshotDate: string | null | undefined;
}

type Status =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; messageKey: string }
  | { kind: "error"; message: string };

const STATUS_MESSAGE_TIMEOUT_MS = 6000;

function messageFor(result: RefreshMarketDataResult, t: (key: string) => string): Status {
  if (result.status === "failed") {
    return { kind: "error", message: `${t("takeSnapshot.failedPrefix")}${result.errors[0] ?? t("takeSnapshot.unknownError")}` };
  }
  if (result.errors.length > 0) {
    return { kind: "success", messageKey: "takeSnapshot.partialErrors" };
  }
  if (result.daily_snapshots_inserted > 0 && result.intraday_snapshots_inserted > 0) {
    return { kind: "success", messageKey: "takeSnapshot.dailyAndIntradayAdded" };
  }
  if (result.intraday_snapshots_inserted > 0) {
    return { kind: "success", messageKey: "takeSnapshot.intradayAdded" };
  }
  return { kind: "success", messageKey: "takeSnapshot.refreshed" };
}

/** Part 10/12: the main dashboard header's "Take New Snapshot" button. Runs the incremental
 * ingest -> ETL cycle plus one new intraday observation per fetched coin (POST
 * /admin/refresh-market-data) -- never a historical backfill, never a wipe -- then, on any
 * non-failed outcome, refetches live current values via onRefreshed. Every successful press adds
 * a distinct intraday snapshot even when daily_snapshots_inserted is 0 (today's daily row already
 * existed). `inFlightRef` blocks a second submit from a rapid double-click that lands before
 * React re-renders the disabled button; the backend's own pipeline lock (see pipeline_runner.py)
 * still guards true cross-tab/cross-client concurrency. */
export function TakeSnapshotButton({ onRefreshed, lastRefreshedAt, latestDailySnapshotDate }: TakeSnapshotButtonProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [intradaySnapshotsToday, setIntradaySnapshotsToday] = useState<number | null>(null);
  const inFlightRef = useRef(false);

  async function handleClick() {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setStatus({ kind: "loading" });

    try {
      const result = await refreshMarketData();
      const next = messageFor(result, t);
      setStatus(next);
      if (result.status !== "failed") {
        setIntradaySnapshotsToday(result.intraday_snapshots_today);
      }
      if (next.kind === "success") {
        onRefreshed();
      }
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : t("common.somethingWentWrong");
      setStatus({ kind: "error", message: `${t("takeSnapshot.failedPrefix")}${detail}` });
    } finally {
      inFlightRef.current = false;
      setTimeout(() => {
        setStatus((current) => (current.kind === "loading" ? current : { kind: "idle" }));
      }, STATUS_MESSAGE_TIMEOUT_MS);
    }
  }

  const loading = status.kind === "loading";

  return (
    <div className="take-snapshot">
      <button
        type="button"
        className="take-snapshot__button"
        onClick={handleClick}
        disabled={loading}
        aria-busy={loading}
      >
        {loading && <span className="status-spinner" aria-hidden="true" />}
        {loading ? t("takeSnapshot.fetching") : t("takeSnapshot.cta")}
      </button>

      <div className="take-snapshot__meta">
        <span className="take-snapshot__last-refreshed">
          {t("takeSnapshot.lastRefreshed")}: {formatDateTime(lastRefreshedAt)}
        </span>
        {latestDailySnapshotDate && (
          <span className="take-snapshot__extra">
            {t("takeSnapshot.latestDailySnapshot")}: {formatDate(latestDailySnapshotDate)}
          </span>
        )}
        {intradaySnapshotsToday !== null && (
          <span className="take-snapshot__extra">
            {t("takeSnapshot.intradaySnapshotsToday")}: {intradaySnapshotsToday}
          </span>
        )}
        {status.kind === "success" && (
          <span className="take-snapshot__status take-snapshot__status--success" role="status">
            {t(status.messageKey)}
          </span>
        )}
        {status.kind === "error" && (
          <span className="take-snapshot__status take-snapshot__status--error" role="alert">
            {status.message}
          </span>
        )}
      </div>
    </div>
  );
}
