import { useTranslation } from "react-i18next";
import type { ConcentrationRisk, PortfolioHealth, PortfolioHealthLevel } from "../api/types";
import { formatNumber } from "../utils/format";
import "./OverviewCards.css";
import "./AIMarketOverviewSection.css";

const PLACEHOLDER = "—";

/** Unsigned percentage formatting for magnitude values (allocation shares, not signed changes),
 * e.g. "41.0%". Returns a placeholder for null/NaN. */
function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return PLACEHOLDER;
  return `${value.toFixed(1)}%`;
}

interface PortfolioHealthCardsProps {
  health: PortfolioHealth;
  numberOfPositions: number;
}

type Tone = "positive" | "negative" | "mixed" | "neutral";

// See ai_portfolio_review_service.classify_portfolio_health -- level is the worse of two signals
// (concentration + diversification), so the badge tone runs green -> gray -> amber -> red as risk rises.
const HEALTH_TONE: Record<PortfolioHealthLevel, Tone> = {
  excellent: "positive",
  good: "positive",
  balanced: "neutral",
  concentrated: "mixed",
  high_risk: "negative",
  very_high_risk: "negative",
};
const HEALTH_EMOJI: Record<PortfolioHealthLevel, string> = {
  excellent: "🟢",
  good: "🟢",
  balanced: "⚪",
  concentrated: "🟡",
  high_risk: "🔴",
  very_high_risk: "🔴",
};

const CONCENTRATION_TONE: Record<ConcentrationRisk, Tone> = {
  low: "positive",
  medium: "neutral",
  high: "negative",
  unknown: "neutral",
};

function Card({ label, value, tone }: { label: string; value: React.ReactNode; tone?: Tone }) {
  return (
    <div className="overview-card">
      <dt>{label}</dt>
      <dd>{tone ? <span className={`ai-status__badge ai-status__badge--${tone}`}>{value}</span> : value}</dd>
    </div>
  );
}

/** "Portfolio Health" status cards -- the deterministic headline read on the AI Portfolio Review
 * tab, reusing OverviewCards.css's grid/card chrome and AIMarketOverviewSection.css's
 * status-badge coloring rather than inventing new styles. Every value here is computed in
 * ai_portfolio_review_service.py; the AI never chooses these. */
export function PortfolioHealthCards({ health, numberOfPositions }: PortfolioHealthCardsProps) {
  const { t } = useTranslation();
  return (
    <dl className="overview-grid">
      <Card
        label={t("ai.portfolioReview.portfolioHealth")}
        tone={HEALTH_TONE[health.level]}
        value={
          <>
            <span aria-hidden="true">{HEALTH_EMOJI[health.level]}</span> {t(`ai.portfolioReview.healthLevel.${health.level}`)}
          </>
        }
      />
      <Card label={t("ai.portfolioReview.diversification")} value={`${formatNumber(health.diversification_score)}/10`} />
      <Card
        label={t("ai.portfolioReview.concentration")}
        tone={CONCENTRATION_TONE[health.concentration_risk]}
        value={t(`ai.coinAnalysis.level.${health.concentration_risk}`)}
      />
      <Card label={t("ai.portfolioReview.cashAllocation")} value={formatPercent(health.cash_allocation_percent)} />
      <Card
        label={t("ai.portfolioReview.largestHolding")}
        value={
          health.largest_holding_symbol
            ? `${health.largest_holding_symbol} (${formatPercent(health.largest_holding_percent)})`
            : PLACEHOLDER
        }
      />
      <Card label={t("ai.portfolioReview.numberOfPositions")} value={formatNumber(numberOfPositions)} />
    </dl>
  );
}
