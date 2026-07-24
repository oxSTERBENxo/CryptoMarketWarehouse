export type RangeOption = "today" | "7d" | "30d" | "90d" | "1y" | "all";
/** Ranges backed by the daily-history endpoint. "today" is backed by the separate intraday endpoint. */
export type DailyRangeOption = Exclude<RangeOption, "today">;

export const RANGE_OPTIONS: { value: RangeOption; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "7d", label: "7D" },
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
  { value: "1y", label: "1Y" },
  { value: "all", label: "All" },
];

export const DEFAULT_RANGE: RangeOption = "30d";

/** Periods accepted by GET /analytics/market-leaders -- every RangeOption except "all", which
 * has no meaningful "first vs last observation" period for a leaderboard. */
export type LeadersRangeOption = Exclude<RangeOption, "all">;

export const LEADERS_RANGE_OPTIONS: { value: LeadersRangeOption; label: string }[] = RANGE_OPTIONS.filter(
  (option): option is { value: LeadersRangeOption; label: string } => option.value !== "all"
);

export const DEFAULT_LEADERS_RANGE: LeadersRangeOption = "7d";

const RANGE_DAYS: Record<Exclude<DailyRangeOption, "all">, number> = {
  "7d": 7,
  "30d": 30,
  "90d": 90,
  "1y": 365,
};

export function isTodayRange(range: RangeOption): range is "today" {
  return range === "today";
}

/** Returns the `from_date` (YYYY-MM-DD) for a daily-history range option relative to `today`, or
 * undefined for "all". Not meaningful for "today" -- callers must branch to the intraday endpoint
 * before calling this (see isTodayRange). */
export function fromDateForRange(range: DailyRangeOption, today: Date = new Date()): string | undefined {
  if (range === "all") return undefined;
  const from = new Date(today);
  from.setDate(from.getDate() - RANGE_DAYS[range]);
  return from.toISOString().slice(0, 10);
}
