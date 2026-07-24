import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getDataRecoveryStatus } from "../api/admin";
import type { DataRecoveryStatus } from "../api/admin";
import "./RecoveryStatusBanner.css";

const POLL_INTERVAL_MS = 4000;
const COMPLETION_MESSAGE_TIMEOUT_MS = 8000;

/** Part 13: compact, non-blocking notice for the startup gap-detection/backfill job. Polls GET
 * /admin/data-recovery-status only while it's actually running, so this never busy-polls forever;
 * shows nothing at all when there was nothing to recover (Part 13: no permanent success banner),
 * and a one-time "up to date" message that clears itself shortly after a run with real gaps
 * finishes. */
export function RecoveryStatusBanner() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<DataRecoveryStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const wasRunningRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const next = await getDataRecoveryStatus();
        if (cancelled) return;

        if (next.status === "running") {
          wasRunningRef.current = true;
        }
        setStatus(next);

        if (next.status === "running") {
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        } else if (wasRunningRef.current) {
          // Only ever transitions here once, right after a run that had real work to do.
          setTimeout(() => setDismissed(true), COMPLETION_MESSAGE_TIMEOUT_MS);
        }
      } catch {
        // Recovery status is a non-critical, best-effort notice -- a failed poll simply stops
        // polling rather than surfacing an error state of its own.
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (!status || dismissed) return null;
  if (status.status === "idle") return null;
  if (status.status !== "running" && status.missing_dates.length === 0) return null;

  if (status.status === "running") {
    const total = status.missing_dates.length;
    const done = status.dates_completed.length;
    return (
      <div className="recovery-banner recovery-banner--running" role="status">
        <span className="status-spinner" aria-hidden="true" />
        {t("recoveryBanner.running", { count: total, done, total })}
      </div>
    );
  }

  if (status.status === "partial_failure") {
    return (
      <div className="recovery-banner recovery-banner--warning" role="status">
        {t("recoveryBanner.partialFailure", { count: status.errors.length })}
      </div>
    );
  }

  return (
    <div className="recovery-banner recovery-banner--success" role="status">
      {t("recoveryBanner.upToDate")}
    </div>
  );
}
