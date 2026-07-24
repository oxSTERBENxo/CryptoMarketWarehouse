import { useState } from "react";
import { useTranslation } from "react-i18next";
import { refreshMarketData } from "../api/admin";
import { ApiError } from "../api/client";
import "./RefreshMarketDataButton.css";

interface RefreshMarketDataButtonProps {
  /** Called once the refresh completes successfully, so the caller can refetch its data. */
  onRefreshed: () => void;
}

type Status =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; messageKey: string }
  | { kind: "error"; message: string };

const STATUS_MESSAGE_TIMEOUT_MS = 6000;

/** Part 4/5: manual "Refresh Market Data" action. Runs only the existing incremental ingest ->
 * ETL pipeline (POST /admin/refresh-market-data) -- never a historical backfill, never a wipe. */
export function RefreshMarketDataButton({ onRefreshed }: RefreshMarketDataButtonProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function handleClick() {
    setStatus({ kind: "loading" });
    try {
      const result = await refreshMarketData();
      const messageKey =
        result.daily_snapshots_inserted > 0 || result.intraday_snapshots_inserted > 0
          ? "refreshMarketData.updated"
          : "refreshMarketData.noNewData";
      setStatus({ kind: "success", messageKey });
      onRefreshed();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : t("common.somethingWentWrong");
      setStatus({ kind: "error", message });
    } finally {
      setTimeout(() => setStatus({ kind: "idle" }), STATUS_MESSAGE_TIMEOUT_MS);
    }
  }

  const loading = status.kind === "loading";

  return (
    <div className="refresh-market-data">
      <button
        type="button"
        className="refresh-market-data__button"
        onClick={handleClick}
        disabled={loading}
      >
        {loading && <span className="status-spinner" aria-hidden="true" />}
        {loading ? t("refreshMarketData.refreshing") : t("refreshMarketData.cta")}
      </button>
      {status.kind === "success" && (
        <span className="refresh-market-data__status refresh-market-data__status--success" role="status">
          {t(status.messageKey)}
        </span>
      )}
      {status.kind === "error" && (
        <span className="refresh-market-data__status refresh-market-data__status--error" role="alert">
          {status.message}
        </span>
      )}
    </div>
  );
}
