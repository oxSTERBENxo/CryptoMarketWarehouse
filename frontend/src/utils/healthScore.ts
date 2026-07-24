import type { PaperPortfolio } from "../api/types";
import type { TranslateFn } from "./achievements";

export interface HealthScoreFactor {
  id: string;
  label: string;
  points: number;
  maxPoints: number;
  detail: string;
}

export interface HealthScore {
  score: number;
  factors: HealthScoreFactor[];
}

const TARGET_ASSET_COUNT = 5;
const CASH_RESERVE_HEALTHY_MIN = 10; // % of total equity
const CASH_RESERVE_HEALTHY_MAX = 40;

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

/**
 * Transparent 0-100 educational health score, not financial advice. Five factors, each capped:
 * - Diversification (25 pts): more distinct assets held is better, up to TARGET_ASSET_COUNT.
 * - Concentration risk (25 pts): inverse of the largest single-asset allocation %.
 * - Cash reserve (20 pts): full points inside a healthy 10-40% cash range, tapering outside it.
 * - Profitable positions (20 pts): share of current holdings that are in unrealized profit.
 * - Assets held (10 pts): a smaller, separate reward for simply holding more than one asset.
 */
export function computeHealthScore(portfolio: PaperPortfolio, t: TranslateFn): HealthScore {
  const holdings = portfolio.holdings;
  const distinctAssets = holdings.length;
  const totalEquity = portfolio.total_equity;

  const diversificationPoints = Math.min(distinctAssets / TARGET_ASSET_COUNT, 1) * 25;

  const maxAllocation = holdings.reduce((max, h) => Math.max(max, h.allocation_percent ?? 0), 0);
  const concentrationPoints = (1 - maxAllocation / 100) * 25;

  const cashPercent = totalEquity > 0 ? (portfolio.cash_balance / totalEquity) * 100 : 100;
  let cashReservePoints: number;
  if (cashPercent >= CASH_RESERVE_HEALTHY_MIN && cashPercent <= CASH_RESERVE_HEALTHY_MAX) {
    cashReservePoints = 20;
  } else {
    const distance =
      cashPercent < CASH_RESERVE_HEALTHY_MIN ? CASH_RESERVE_HEALTHY_MIN - cashPercent : cashPercent - CASH_RESERVE_HEALTHY_MAX;
    cashReservePoints = Math.max(0, 20 - distance * 0.5);
  }

  const profitableHoldings = holdings.filter((h) => (h.unrealized_profit ?? 0) > 0).length;
  const profitablePoints = distinctAssets > 0 ? (profitableHoldings / distinctAssets) * 20 : 0;

  const assetCountPoints = (Math.min(distinctAssets, TARGET_ASSET_COUNT) / TARGET_ASSET_COUNT) * 10;

  const factors: HealthScoreFactor[] = [
    {
      id: "diversification",
      label: t("portfolio.health.diversification.label"),
      points: round1(diversificationPoints),
      maxPoints: 25,
      detail: t("portfolio.health.diversification.detail", { count: distinctAssets, target: TARGET_ASSET_COUNT }),
    },
    {
      id: "concentration",
      label: t("portfolio.health.concentration.label"),
      points: round1(concentrationPoints),
      maxPoints: 25,
      detail: t("portfolio.health.concentration.detail", { percent: maxAllocation.toFixed(1) }),
    },
    {
      id: "cash-reserve",
      label: t("portfolio.health.cashReserve.label"),
      points: round1(cashReservePoints),
      maxPoints: 20,
      detail: t("portfolio.health.cashReserve.detail", {
        percent: cashPercent.toFixed(1),
        min: CASH_RESERVE_HEALTHY_MIN,
        max: CASH_RESERVE_HEALTHY_MAX,
      }),
    },
    {
      id: "profitable-positions",
      label: t("portfolio.health.profitablePositions.label"),
      points: round1(profitablePoints),
      maxPoints: 20,
      detail:
        distinctAssets > 0
          ? t("portfolio.health.profitablePositions.detail", { profitable: profitableHoldings, total: distinctAssets })
          : t("portfolio.health.profitablePositions.noPositions"),
    },
    {
      id: "asset-count",
      label: t("portfolio.health.assetCount.label"),
      points: round1(assetCountPoints),
      maxPoints: 10,
      detail: t("portfolio.health.assetCount.detail", { count: distinctAssets, target: TARGET_ASSET_COUNT }),
    },
  ];

  const score = Math.round(factors.reduce((sum, f) => sum + f.points, 0));

  return { score: Math.max(0, Math.min(100, score)), factors };
}
