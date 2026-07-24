import type { ExplorerCondition, ExplorerMetric, ExplorerSortField } from "../api/types";

/** One selectable analysis: a (metric, condition) pair registered in the backend's
 * analytics_explorer_service.ANALYSES, plus what the form needs to render it. Labels are i18n
 * keys (translated at render time in AnalyticsExplorer.tsx) rather than raw strings, since this
 * module has no access to the active i18next instance. */
export interface AnalysisOption {
  metric: ExplorerMetric;
  condition: ExplorerCondition;
  labelKey: string;
  /** Whether the backend requires a threshold for this analysis, and how to label the input. */
  thresholdLabelKey: string | null;
  thresholdPlaceholderKey?: string;
}

export const METRIC_OPTIONS: { value: ExplorerMetric; labelKey: string }[] = [
  { value: "price", labelKey: "explorer.metrics.price" },
  { value: "volume", labelKey: "explorer.metrics.volume" },
  { value: "market_cap_rank", labelKey: "explorer.metrics.marketCapRank" },
  { value: "volatility", labelKey: "explorer.metrics.volatility" },
];

/** Mirrors the supported combinations in analytics_explorer_service.ANALYSES. The Analysis Type
 * dropdown only ever offers conditions valid for the selected metric, so the backend's
 * unsupported-combination 400 is unreachable from this form. */
export const ANALYSIS_OPTIONS: AnalysisOption[] = [
  {
    metric: "price",
    condition: "increased_by_percent",
    labelKey: "explorer.analyses.priceIncreasedByPercent.label",
    thresholdLabelKey: "explorer.analyses.priceIncreasedByPercent.thresholdLabel",
    thresholdPlaceholderKey: "explorer.analyses.priceIncreasedByPercent.thresholdPlaceholder",
  },
  {
    metric: "price",
    condition: "decreased_by_percent",
    labelKey: "explorer.analyses.priceDecreasedByPercent.label",
    thresholdLabelKey: "explorer.analyses.priceDecreasedByPercent.thresholdLabel",
    thresholdPlaceholderKey: "explorer.analyses.priceDecreasedByPercent.thresholdPlaceholder",
  },
  {
    metric: "price",
    condition: "increased_by_amount",
    labelKey: "explorer.analyses.priceIncreasedByAmount.label",
    thresholdLabelKey: "explorer.analyses.priceIncreasedByAmount.thresholdLabel",
    thresholdPlaceholderKey: "explorer.analyses.priceIncreasedByAmount.thresholdPlaceholder",
  },
  {
    metric: "price",
    condition: "decreased_by_amount",
    labelKey: "explorer.analyses.priceDecreasedByAmount.label",
    thresholdLabelKey: "explorer.analyses.priceDecreasedByAmount.thresholdLabel",
    thresholdPlaceholderKey: "explorer.analyses.priceDecreasedByAmount.thresholdPlaceholder",
  },
  { metric: "price", condition: "top_n", labelKey: "explorer.analyses.priceTopN.label", thresholdLabelKey: null },
  { metric: "price", condition: "bottom_n", labelKey: "explorer.analyses.priceBottomN.label", thresholdLabelKey: null },
  { metric: "volume", condition: "top_n", labelKey: "explorer.analyses.volumeTopN.label", thresholdLabelKey: null },
  {
    metric: "market_cap_rank",
    condition: "improved_by",
    labelKey: "explorer.analyses.rankImprovedBy.label",
    thresholdLabelKey: "explorer.analyses.rankImprovedBy.thresholdLabel",
    thresholdPlaceholderKey: "explorer.analyses.rankImprovedBy.thresholdPlaceholder",
  },
  {
    metric: "market_cap_rank",
    condition: "declined_by",
    labelKey: "explorer.analyses.rankDeclinedBy.label",
    thresholdLabelKey: "explorer.analyses.rankDeclinedBy.thresholdLabel",
    thresholdPlaceholderKey: "explorer.analyses.rankDeclinedBy.thresholdPlaceholder",
  },
  { metric: "volatility", condition: "top_n", labelKey: "explorer.analyses.volatilityTopN.label", thresholdLabelKey: null },
  {
    metric: "volatility",
    condition: "bottom_n",
    labelKey: "explorer.analyses.volatilityBottomN.label",
    thresholdLabelKey: null,
  },
];

export function analysesForMetric(metric: ExplorerMetric): AnalysisOption[] {
  return ANALYSIS_OPTIONS.filter((option) => option.metric === metric);
}

export function findAnalysis(metric: ExplorerMetric, condition: ExplorerCondition): AnalysisOption | undefined {
  return ANALYSIS_OPTIONS.find((option) => option.metric === metric && option.condition === condition);
}

export const SORT_OPTIONS: { value: ExplorerSortField; labelKey: string }[] = [
  { value: "percent_change", labelKey: "explorer.sort.percentChange" },
  { value: "dollar_change", labelKey: "explorer.sort.dollarChange" },
  { value: "end_price", labelKey: "explorer.sort.endPrice" },
  { value: "avg_volume", labelKey: "explorer.sort.avgVolume" },
  { value: "rank_change", labelKey: "explorer.sort.rankChange" },
  { value: "market_cap", labelKey: "explorer.sort.marketCap" },
  { value: "volatility", labelKey: "explorer.sort.volatility" },
];
