import type { DailyRangeOption, RangeOption } from "./dateRange";
import { formatNumber } from "./format";
import i18n from "../i18n";

/** Normalized period statistics shared by the daily (server-computed) and intraday
 * (client-computed) code paths, so the summary-card and header JSX don't need to branch. */
export interface PeriodSummary {
  minPrice: number;
  maxPrice: number;
  avgPrice: number;
  percentChange: number | null;
  observationCount: number;
  firstLabel: string;
  latestLabel: string;
}

export function rangeRequestedDays(range: DailyRangeOption): number | null {
  if (range === "7d") return 7;
  if (range === "30d") return 30;
  if (range === "90d") return 90;
  if (range === "1y") return 365;
  return null; // "all"
}

/** Builds the "Showing X of Y requested..." / "Intraday data collected from..." coverage line,
 * so users can see at a glance whether 90D/1Y/All are actually showing more than 30D, or whether
 * coverage is currently limited -- never silently making a wider range look identical. Reads
 * directly off the shared i18n singleton (rather than taking a `t` param) so this plain utility
 * stays callable without a React tree, while still reflecting whatever language is active --
 * callers that render its result (CoinDetails) already re-render on language change via their own
 * useTranslation() subscription. */
export function buildCoverageMessage(
  isToday: boolean,
  range: RangeOption,
  actualCount: number,
  summary: PeriodSummary | null
): string {
  const t = i18n.t.bind(i18n);

  if (isToday) {
    if (actualCount === 0) return t("coinDetails.coverage.todayNone");
    return t("coinDetails.coverage.todayWithCount", {
      count: actualCount,
      formattedCount: formatNumber(actualCount),
      first: summary?.firstLabel,
      latest: summary?.latestLabel,
    });
  }

  const requestedDays = rangeRequestedDays(range as DailyRangeOption);
  if (requestedDays === null) {
    return t("coinDetails.coverage.allAvailable", { count: actualCount, formattedCount: formatNumber(actualCount) });
  }
  if (actualCount < requestedDays) {
    return t("coinDetails.coverage.partial", { formattedCount: formatNumber(actualCount), requested: requestedDays });
  }
  return t("coinDetails.coverage.full", { requested: requestedDays });
}
