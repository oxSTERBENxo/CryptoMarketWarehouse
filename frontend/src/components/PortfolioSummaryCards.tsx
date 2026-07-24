import { useTranslation } from "react-i18next";
import type { PortfolioSummary } from "../api/types";
import { formatSignedPercent, formatSignedUsd, formatUsd } from "../utils/format";
import "./OverviewCards.css";
import "./PortfolioSummaryCards.css";

interface PortfolioSummaryCardsProps {
  summary: PortfolioSummary;
}

function profitClass(value: number | null): string {
  if (value === null || value === 0) return "profit-neutral";
  return value > 0 ? "profit-positive" : "profit-negative";
}

export function PortfolioSummaryCards({ summary }: PortfolioSummaryCardsProps) {
  const { t } = useTranslation();
  return (
    <dl className="overview-grid">
      <div className="overview-card">
        <dt>{t("portfolio.summary.totalValue")}</dt>
        <dd>{formatUsd(summary.total_value)}</dd>
      </div>
      <div className="overview-card">
        <dt>{t("portfolio.summary.totalCostBasis")}</dt>
        <dd>{formatUsd(summary.total_cost_basis)}</dd>
      </div>
      <div className="overview-card">
        <dt>{t("portfolio.summary.unrealizedProfitLoss")}</dt>
        <dd className={profitClass(summary.total_unrealized_profit)}>
          {formatSignedUsd(summary.total_unrealized_profit)}
        </dd>
      </div>
      <div className="overview-card">
        <dt>{t("portfolio.summary.profitPercent")}</dt>
        <dd className={profitClass(summary.total_unrealized_percent)}>
          {formatSignedPercent(summary.total_unrealized_percent)}
        </dd>
      </div>
    </dl>
  );
}
