import { useTranslation } from "react-i18next";
import type { MarketMetrics, MarketStatus } from "../api/types";
import { changeClass, formatCompactUsd, formatDateTime, formatNumber, formatSignedPercent } from "../utils/format";
import "./PortfolioSummaryCards.css";
import "./OverviewCards.css";
import "./AIMarketOverviewSection.css";

interface AIMarketOverviewSectionProps {
  status: MarketStatus;
  metrics: MarketMetrics;
}

/** Section 1 (Market Status Header) + Section 2 (Market Metric Cards) of the redesigned AI Market
 * Summary card. Every value here is deterministic (see ai_market_summary_service.py) -- the badge,
 * headline, and counts are computed in application code, never decided by the model. This is the
 * "understand it in a few seconds" part of the card, so it's never collapsible. */
export function AIMarketOverviewSection({ status, metrics }: AIMarketOverviewSectionProps) {
  const { t } = useTranslation();
  return (
    <div className="ai-overview">
      <div className="ai-status">
        <span className={`ai-status__badge ai-status__badge--${status.direction}`}>
          {t(`ai.overview.direction.${status.direction}`)}
        </span>
        <p className="ai-status__headline">{status.headline}</p>
      </div>

      <dl className="ai-status__chips">
        <div className="ai-status__chip">
          <dt>{t("ai.overview.avgChange24h")}</dt>
          <dd className={changeClass(status.average_change_24h)}>{formatSignedPercent(status.average_change_24h)}</dd>
        </div>
        <div className="ai-status__chip">
          <dt>{t("ai.overview.gainers")}</dt>
          <dd className="profit-positive">{formatNumber(status.gainers_count)}</dd>
        </div>
        <div className="ai-status__chip">
          <dt>{t("ai.overview.losers")}</dt>
          <dd className="profit-negative">{formatNumber(status.losers_count)}</dd>
        </div>
        <div className="ai-status__chip">
          <dt>{t("ai.overview.unchanged")}</dt>
          <dd>{formatNumber(status.unchanged_count)}</dd>
        </div>
        <div className="ai-status__chip">
          <dt>{t("ai.overview.tracked")}</dt>
          <dd>{formatNumber(status.coins_tracked)}</dd>
        </div>
        <div className="ai-status__chip">
          <dt>{t("ai.overview.snapshot")}</dt>
          <dd>{formatDateTime(status.snapshot_time)}</dd>
        </div>
      </dl>

      <dl className="overview-grid ai-metric-cards">
        <div className="overview-card">
          <dt>{t("ai.overview.totalMarketCap")}</dt>
          <dd>{formatCompactUsd(metrics.total_market_cap)}</dd>
        </div>
        <div className="overview-card">
          <dt>{t("ai.overview.totalVolume24h")}</dt>
          <dd>{formatCompactUsd(metrics.total_volume_24h)}</dd>
        </div>
        <div className="overview-card">
          <dt>{t("ai.overview.averageChange24h")}</dt>
          <dd className={changeClass(status.average_change_24h)}>{formatSignedPercent(status.average_change_24h)}</dd>
        </div>
        <div className="overview-card">
          <dt>{t("ai.overview.gainersVsLosers")}</dt>
          <dd>
            <span className="profit-positive">{formatNumber(status.gainers_count)}</span>
            <span className="ai-metric-cards__divider"> / </span>
            <span className="profit-negative">{formatNumber(status.losers_count)}</span>
          </dd>
        </div>
      </dl>
    </div>
  );
}
