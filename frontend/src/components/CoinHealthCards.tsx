import { useTranslation } from "react-i18next";
import type { CoinDeterministicMetrics, LiquidityLevel, PriceTrend, VolatilityLevel } from "../api/types";
import "./OverviewCards.css";
import "./AIMarketOverviewSection.css";

interface CoinHealthCardsProps {
  metrics: CoinDeterministicMetrics;
}

type Tone = "positive" | "negative" | "neutral";

const TREND_TONE: Record<PriceTrend, Tone> = {
  bullish: "positive",
  bearish: "negative",
  neutral: "neutral",
  unknown: "neutral",
};

// Calmer (low) volatility reads as favorable, elevated (high) volatility as a risk signal.
const VOLATILITY_TONE: Record<VolatilityLevel, Tone> = {
  low: "positive",
  medium: "neutral",
  high: "negative",
  unknown: "neutral",
};

// Higher liquidity is generally favorable (easier to trade without moving the price).
const LIQUIDITY_TONE: Record<LiquidityLevel, Tone> = {
  low: "negative",
  medium: "neutral",
  high: "positive",
  unknown: "neutral",
};

function HealthCard({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  return (
    <div className="overview-card">
      <dt>{label}</dt>
      <dd>
        <span className={`ai-status__badge ai-status__badge--${tone}`}>{value}</span>
      </dd>
    </div>
  );
}

/** "Coin Health" status cards: Price Trend, Volatility, Liquidity, and Market Tier as compact,
 * at-a-glance badges -- reuses OverviewCards.css's grid/card chrome and
 * AIMarketOverviewSection.css's status-badge coloring rather than inventing new styles. Every
 * value is deterministic (see ai_coin_analysis_service.py); the AI never chooses these. */
export function CoinHealthCards({ metrics }: CoinHealthCardsProps) {
  const { t } = useTranslation();
  return (
    <dl className="overview-grid coin-health-cards">
      <HealthCard
        label={t("ai.coinAnalysis.priceTrend")}
        value={t(`ai.coinAnalysis.trend.${metrics.price_trend}`)}
        tone={TREND_TONE[metrics.price_trend]}
      />
      <HealthCard
        label={t("ai.coinAnalysis.volatility")}
        value={t(`ai.coinAnalysis.level.${metrics.volatility_level}`)}
        tone={VOLATILITY_TONE[metrics.volatility_level]}
      />
      <HealthCard
        label={t("ai.coinAnalysis.liquidity")}
        value={t(`ai.coinAnalysis.level.${metrics.liquidity_level}`)}
        tone={LIQUIDITY_TONE[metrics.liquidity_level]}
      />
      <HealthCard
        label={t("ai.coinAnalysis.marketTier")}
        value={t(`ai.coinAnalysis.tier.${metrics.market_cap_tier}`)}
        tone="neutral"
      />
    </dl>
  );
}
