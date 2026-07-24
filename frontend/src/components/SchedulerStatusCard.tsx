import { useTranslation } from "react-i18next";
import { getSchedulerHealth } from "../api/health";
import { useApiData } from "../hooks/useApiData";
import { formatDate, formatDateTime } from "../utils/format";
import { SectionStatus } from "./SectionStatus";
import "./SchedulerStatusCard.css";

interface SchedulerStatusCardProps {
  /** Snapshot date of the most recently loaded warehouse data, from /analytics/overview. */
  latestSnapshotDate: string | null | undefined;
}

/** Small read-only status card: latest warehouse snapshot, whether the scheduler is enabled,
 * and when it next runs. No controls — automated collection is configured via environment
 * variables, not from the dashboard. */
export function SchedulerStatusCard({ latestSnapshotDate }: SchedulerStatusCardProps) {
  const { t } = useTranslation();
  const health = useApiData(getSchedulerHealth);

  return (
    <section aria-labelledby="scheduler-status-heading" className="scheduler-status-section">
      <h2 id="scheduler-status-heading">{t("schedulerStatus.title")}</h2>
      <SectionStatus loading={health.loading} error={health.error} isEmpty={!health.data} onRetry={health.retry}>
        {health.data && (
          <dl className="scheduler-status-card">
            <div className="scheduler-status-row">
              <dt>{t("schedulerStatus.latestSnapshot")}</dt>
              <dd>{formatDate(latestSnapshotDate)}</dd>
            </div>
            <div className="scheduler-status-row">
              <dt>{t("schedulerStatus.automaticCollection")}</dt>
              <dd>
                <span
                  className={`scheduler-status-badge ${
                    health.data.enabled ? "scheduler-status-badge--on" : "scheduler-status-badge--off"
                  }`}
                >
                  {health.data.enabled ? t("schedulerStatus.enabled") : t("schedulerStatus.disabled")}
                </span>
              </dd>
            </div>
            <div className="scheduler-status-row">
              <dt>{t("schedulerStatus.nextRun")}</dt>
              <dd>{health.data.enabled ? formatDateTime(health.data.next_run_time) : "—"}</dd>
            </div>
          </dl>
        )}
      </SectionStatus>
    </section>
  );
}
