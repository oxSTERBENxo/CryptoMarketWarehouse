import { useTranslation } from "react-i18next";
import type { CurrentMarketSnapshot } from "../api/types";
import { formatCompactUsd, formatDateTime, formatNumber } from "../utils/format";
import { SectionStatus } from "./SectionStatus";
import "./OverviewCards.css";

interface OverviewCardsProps {
  overview: CurrentMarketSnapshot | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

/** Live current-market overview (GET /analytics/current-market): unlike the daily-grain
 * MarketOverview, these totals reflect the most recent ingestion run immediately, even when the
 * warehouse's (date_key, coin_key) guard means no new daily row landed. */
export function OverviewCards({ overview, loading, error, onRetry }: OverviewCardsProps) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="overview-heading" className="overview-section">
      <h2 id="overview-heading">{t("dashboard.overview.title")}</h2>
      <SectionStatus loading={loading} error={error} isEmpty={!overview} onRetry={onRetry}>
        {overview && (
          <dl className="overview-grid">
            <div className="overview-card">
              <dt>{t("dashboard.overview.lastRefreshed")}</dt>
              <dd>{formatDateTime(overview.refreshed_at)}</dd>
            </div>
            <div className="overview-card">
              <dt>{t("dashboard.overview.coinsTracked")}</dt>
              <dd>{formatNumber(overview.coin_count)}</dd>
            </div>
            <div className="overview-card">
              <dt>{t("dashboard.overview.totalMarketCap")}</dt>
              <dd>{formatCompactUsd(overview.total_market_cap_usd)}</dd>
            </div>
            <div className="overview-card">
              <dt>{t("dashboard.overview.totalVolume")}</dt>
              <dd>{formatCompactUsd(overview.total_volume_24h_usd)}</dd>
            </div>
          </dl>
        )}
      </SectionStatus>
    </section>
  );
}
