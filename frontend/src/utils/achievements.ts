import type { PaperPortfolio, PaperTransaction } from "../api/types";

export interface Achievement {
  id: string;
  label: string;
  description: string;
  earned: boolean;
}

/** i18next's TFunction shape, narrowed to what this module needs -- kept dependency-light since
 * this is a plain utility module, not a component. */
export type TranslateFn = (key: string, options?: Record<string, unknown>) => string;

const DIAMOND_HANDS_DAYS = 7;

/**
 * Achievement rules, computed purely from real application state (never fabricated):
 * - First Trade: at least one transaction has ever been executed.
 * - Diversified: 3 or more distinct assets currently held.
 * - Diamond Hands: some currently-held asset has a BUY at least 7 days old — a date-based proxy
 *   for "held across 7+ daily snapshots", since the app has no daily portfolio-snapshot table.
 * - Profitable Portfolio: combined realized + unrealized profit is positive.
 * - Five Trades Completed: 5 or more transactions total.
 * - Balanced Portfolio: holds at least one asset, and no single asset exceeds 50% of equity.
 */
export function computeAchievements(
  portfolio: PaperPortfolio,
  transactions: PaperTransaction[],
  t: TranslateFn
): Achievement[] {
  const heldSymbols = new Set(portfolio.holdings.map((h) => h.coin_symbol));
  const now = Date.now();

  const hasDiamondHands = transactions.some((tx) => {
    if (tx.transaction_type !== "BUY" || !heldSymbols.has(tx.coin_symbol)) return false;
    const ageDays = (now - new Date(tx.executed_at).getTime()) / (1000 * 60 * 60 * 24);
    return ageDays >= DIAMOND_HANDS_DAYS;
  });

  const maxAllocation = portfolio.holdings.reduce((max, h) => Math.max(max, h.allocation_percent ?? 0), 0);

  return [
    {
      id: "first-trade",
      label: t("portfolio.achievements.firstTrade.label"),
      description: t("portfolio.achievements.firstTrade.description"),
      earned: transactions.length >= 1,
    },
    {
      id: "diversified",
      label: t("portfolio.achievements.diversified.label"),
      description: t("portfolio.achievements.diversified.description"),
      earned: portfolio.holdings.length >= 3,
    },
    {
      id: "diamond-hands",
      label: t("portfolio.achievements.diamondHands.label"),
      description: t("portfolio.achievements.diamondHands.description", { days: DIAMOND_HANDS_DAYS }),
      earned: hasDiamondHands,
    },
    {
      id: "profitable-portfolio",
      label: t("portfolio.achievements.profitablePortfolio.label"),
      description: t("portfolio.achievements.profitablePortfolio.description"),
      earned: portfolio.realized_profit + portfolio.unrealized_profit > 0,
    },
    {
      id: "five-trades",
      label: t("portfolio.achievements.fiveTrades.label"),
      description: t("portfolio.achievements.fiveTrades.description"),
      earned: transactions.length >= 5,
    },
    {
      id: "balanced-portfolio",
      label: t("portfolio.achievements.balancedPortfolio.label"),
      description: t("portfolio.achievements.balancedPortfolio.description"),
      earned: portfolio.holdings.length > 0 && maxAllocation <= 50,
    },
  ];
}
