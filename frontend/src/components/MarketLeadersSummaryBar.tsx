import { useTranslation } from "react-i18next";
import type { MarketLeadersSummary } from "../api/types";
import { formatDateTime, formatNumber, formatSignedPercent } from "../utils/format";
import "./OverviewCards.css";
import "./PortfolioSummaryCards.css";
import "./MarketLeadersSummaryBar.css";

interface MarketLeadersSummaryBarProps {
  summary: MarketLeadersSummary;
}

function changeClass(value: number | null): string {
  if (value === null || value === 0) return "profit-neutral";
  return value > 0 ? "profit-positive" : "profit-negative";
}

/** Part 6: the always-on-top summary bar -- total tracked coins, when the warehouse was last
 * loaded, and today's specific best/worst performer + average movement (independent of whichever
 * period is selected below). */
export function MarketLeadersSummaryBar({ summary }: MarketLeadersSummaryBarProps) {
  const { t } = useTranslation();

  function performerLabel(entry: MarketLeadersSummary["today_best_performer"]): string {
    if (!entry) return t("marketLeaders.noIntradayDataToday");
    return `${entry.name} ${formatSignedPercent(entry.percent_change)}`;
  }

  return (
    <section aria-labelledby="leaders-summary-heading" className="overview-section leaders-summary">
      <h2 id="leaders-summary-heading">{t("marketLeaders.snapshotTitle")}</h2>
      <dl className="overview-grid leaders-summary__grid">
        <div className="overview-card">
          <dt>{t("marketLeaders.totalTrackedCoins")}</dt>
          <dd>{formatNumber(summary.total_tracked_coins)}</dd>
        </div>
        <div className="overview-card">
          <dt>{t("marketLeaders.latestUpdate")}</dt>
          <dd>{formatDateTime(summary.latest_update_at)}</dd>
        </div>
        <div className="overview-card">
          <dt>{t("marketLeaders.todaysBestPerformer")}</dt>
          <dd>
            <span className={changeClass(summary.today_best_performer?.percent_change ?? null)}>
              {performerLabel(summary.today_best_performer)}
            </span>
          </dd>
        </div>
        <div className="overview-card">
          <dt>{t("marketLeaders.todaysWorstPerformer")}</dt>
          <dd>
            <span className={changeClass(summary.today_worst_performer?.percent_change ?? null)}>
              {performerLabel(summary.today_worst_performer)}
            </span>
          </dd>
        </div>
        <div className="overview-card">
          <dt>{t("marketLeaders.averageMarketMovement")}</dt>
          <dd>
            <span className={changeClass(summary.average_market_movement_percent)}>
              {formatSignedPercent(summary.average_market_movement_percent)}
            </span>
          </dd>
        </div>
      </dl>
    </section>
  );
}
