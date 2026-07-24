import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { getHistory, getHistorySummary, getIntradayToday } from "../api/analytics";
import type { CoinHistorySummary, CoinSnapshot, IntradaySnapshot } from "../api/types";
import { useApiData } from "../hooks/useApiData";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { InsufficientHistoryCard } from "../components/InsufficientHistoryCard";
import { AICoinAnalysisCard } from "../components/AICoinAnalysisCard";
import { CoinLogo } from "../components/CoinLogo";
import { RangeSelector } from "../components/RangeSelector";
import { MetricChart } from "../components/MetricChart";
import type { MetricChartPoint } from "../components/MetricChart";
import { DEFAULT_RANGE, RANGE_OPTIONS, fromDateForRange, isTodayRange } from "../utils/dateRange";
import type { DailyRangeOption, RangeOption } from "../utils/dateRange";
import { buildCoverageMessage } from "../utils/coverage";
import type { PeriodSummary } from "../utils/coverage";
import {
  formatCompactUsd,
  formatCryptoPrice,
  formatDate,
  formatNumber,
  formatRank,
  formatSignedPercent,
  formatTime,
} from "../utils/format";
import "../components/OverviewCards.css";
import "./CoinDetails.css";

const MIN_OBSERVATIONS_FOR_CHART = 2;

function summarizeIntraday(rows: IntradaySnapshot[]): PeriodSummary | null {
  if (rows.length === 0) return null;
  const prices = rows.map((r) => r.price_usd);
  const first = rows[0];
  const latest = rows[rows.length - 1];
  const percentChange = first.price_usd === 0 ? null : ((latest.price_usd - first.price_usd) / first.price_usd) * 100;
  return {
    minPrice: Math.min(...prices),
    maxPrice: Math.max(...prices),
    avgPrice: prices.reduce((a, b) => a + b, 0) / prices.length,
    percentChange,
    observationCount: rows.length,
    firstLabel: formatTime(first.observation_timestamp),
    latestLabel: formatTime(latest.observation_timestamp),
  };
}

function summarizeDaily(summary: CoinHistorySummary | null): PeriodSummary | null {
  if (!summary) return null;
  return {
    minPrice: summary.min_price,
    maxPrice: summary.max_price,
    avgPrice: summary.avg_price,
    percentChange: summary.percent_change,
    observationCount: summary.observation_count,
    firstLabel: formatDate(summary.period_start_date),
    latestLabel: formatDate(summary.period_end_date),
  };
}

function changeClass(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return "profit-neutral";
  return value > 0 ? "profit-positive" : "profit-negative";
}

/** Coin Details range: the standard presets, plus "custom" when the page was opened with
 * ?from=YYYY-MM-DD&to=YYYY-MM-DD (the Analytics Explorer's row navigation) -- the chart then
 * opens on exactly the analyzed date range instead of a preset. */
type DetailsRange = RangeOption | "custom";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function CoinDetails() {
  const { t } = useTranslation();
  const { symbol = "" } = useParams<{ symbol: string }>();
  const [searchParams] = useSearchParams();
  const customFrom = searchParams.get("from");
  const customTo = searchParams.get("to");
  const hasCustomRange = ISO_DATE.test(customFrom ?? "") && ISO_DATE.test(customTo ?? "");
  const [range, setRange] = useState<DetailsRange>(hasCustomRange ? "custom" : DEFAULT_RANGE);

  const isToday = range !== "custom" && isTodayRange(range);
  const isCustom = range === "custom";
  const dailyFromDate = useMemo(
    () =>
      isCustom ? customFrom ?? undefined : isToday ? undefined : fromDateForRange(range as DailyRangeOption),
    [range, isToday, isCustom, customFrom]
  );
  const dailyToDate = isCustom ? customTo ?? undefined : undefined;

  const rangeOptions = useMemo(
    () =>
      hasCustomRange
        ? [
            { value: "custom" as DetailsRange, label: t("coinDetails.customRange") },
            ...(RANGE_OPTIONS as { value: DetailsRange; label: string }[]),
          ]
        : undefined,
    [hasCustomRange, t]
  );

  // Exactly one of these two fires a real network request per range change: switching between
  // Today and a daily range never issues both, and never duplicates the previous range's request.
  const history = useApiData<CoinSnapshot[]>(
    () =>
      isToday
        ? Promise.resolve([])
        : getHistory(symbol, { order: "asc", fromDate: dailyFromDate, toDate: dailyToDate }),
    [symbol, range]
  );
  const summary = useApiData<CoinHistorySummary | null>(
    () =>
      isToday
        ? Promise.resolve(null)
        : getHistorySummary(symbol, { fromDate: dailyFromDate, toDate: dailyToDate }),
    [symbol, range]
  );
  const intraday = useApiData<IntradaySnapshot[]>(
    () => (isToday ? getIntradayToday(symbol) : Promise.resolve([])),
    [symbol, range]
  );
  // Identity lookup (name, rank, market cap, latest daily snapshot date) for the header card when
  // on the Today range, since intraday observations carry no rank. Only fires for Today, and only
  // refetches when the coin itself changes -- not on every Today<->daily toggle.
  const identity = useApiData<CoinSnapshot[]>(
    () => (isToday ? getHistory(symbol, { order: "desc", limit: 1 }) : Promise.resolve([])),
    [symbol, isToday]
  );

  const dailyRows = history.data ?? [];
  const intradayRows = intraday.data ?? [];
  const latestDaily = isToday ? identity.data?.[0] : dailyRows[dailyRows.length - 1];
  const firstDaily = dailyRows[0];

  const loading = isToday ? intraday.loading : history.loading;
  const error = isToday ? intraday.error : history.error;
  const retry = isToday ? intraday.retry : history.retry;

  const periodSummary = isToday ? summarizeIntraday(intradayRows) : summarizeDaily(summary.data);
  const observationCount = isToday ? intradayRows.length : summary.data?.observation_count ?? dailyRows.length;
  const hasEnoughForChart = observationCount >= MIN_OBSERVATIONS_FOR_CHART;
  const rowCount = isToday ? intradayRows.length : dailyRows.length;

  const priceData: MetricChartPoint[] = isToday
    ? intradayRows.map((row) => ({ date: row.observation_timestamp, value: row.price_usd }))
    : dailyRows.map((row) => ({ date: row.snapshot_date, value: row.price_usd }));
  const volumeData: MetricChartPoint[] = isToday
    ? intradayRows.map((row) => ({ date: row.observation_timestamp, value: row.volume_24h_usd }))
    : dailyRows.map((row) => ({ date: row.snapshot_date, value: row.volume_24h_usd }));

  const heading = latestDaily ? latestDaily.name : symbol.toUpperCase();
  const symbolBadge = latestDaily ? latestDaily.symbol.toUpperCase() : symbol.toUpperCase();
  const periodLabel = isToday
    ? t("coinDetails.periods.today")
    : isCustom
      ? t("coinDetails.periods.custom")
      : range === "all"
        ? t("coinDetails.periods.all")
        : range === "7d"
          ? t("coinDetails.periods.7d")
          : range === "30d"
            ? t("coinDetails.periods.30d")
            : range === "90d"
              ? t("coinDetails.periods.90d")
              : t("coinDetails.periods.1y");
  const priceSubtitle = periodSummary
    ? t("coinDetails.priceSubtitle", { change: formatSignedPercent(periodSummary.percentChange), period: periodLabel })
    : undefined;
  const headerPrice = isToday && intradayRows.length > 0 ? intradayRows[intradayRows.length - 1].price_usd : latestDaily?.price_usd;
  // A custom range has no "requested days" preset to compare against, so coverage reports it
  // like "all": every available observation in the range.
  const coverageMessage = buildCoverageMessage(isToday, isCustom ? "all" : range, rowCount, periodSummary);

  return (
    <main className="coin-details">
      <Link to="/" className="back-link">
        ← {t("notFound.backLink")}
      </Link>

      {loading && <LoadingState label={isToday ? t("coinDetails.loadingIntraday") : t("coinDetails.loadingHistory")} />}

      {!loading && error && <ErrorState message={error} onRetry={retry} />}

      {!loading && !error && (
        <>
          {latestDaily && (
            <header className="coin-details__header">
              <div className="coin-details__heading">
                <h1 className="coin-details__title">
                  <CoinLogo src={latestDaily.image_url} name={heading} size={36} />
                  {heading} <span className="coin-details__badge">{symbolBadge}</span>
                </h1>
                <div className="coin-details__price-row">
                  <span className="coin-details__price">{formatCryptoPrice(headerPrice)}</span>
                  {periodSummary && periodSummary.percentChange !== null && (
                    <span className={`coin-details__change ${changeClass(periodSummary.percentChange)}`}>
                      {formatSignedPercent(periodSummary.percentChange)}
                    </span>
                  )}
                </div>
              </div>
              <dl className="coin-details__meta-row">
                <div>
                  <dt>{t("table.rank")}</dt>
                  <dd>{formatRank(latestDaily.market_cap_rank)}</dd>
                </div>
                <div>
                  <dt>{t("table.marketCap")}</dt>
                  <dd>{formatCompactUsd(latestDaily.market_cap_usd)}</dd>
                </div>
                <div>
                  <dt>{t("table.volume24h")}</dt>
                  <dd>{formatCompactUsd(latestDaily.volume_24h_usd)}</dd>
                </div>
                <div>
                  <dt>{t("coinDetails.latestDailySnapshot")}</dt>
                  <dd>{formatDate(latestDaily.snapshot_date)}</dd>
                </div>
              </dl>
            </header>
          )}

          <div className="coin-details__range-row">
            <RangeSelector value={range} onChange={setRange} options={rangeOptions} />
            <span className={`coin-details__mode-badge coin-details__mode-badge--${isToday ? "intraday" : "daily"}`}>
              {isToday ? t("coinDetails.intraday") : t("coinDetails.daily")}
            </span>
          </div>
          <p className="coin-details__coverage">{coverageMessage}</p>

          {rowCount === 0 ? (
            <EmptyState
              message={isToday ? t("coinDetails.emptyToday") : t("coinDetails.emptyDaily")}
            />
          ) : !hasEnoughForChart ? (
            <InsufficientHistoryCard
              price={isToday ? intradayRows[0].price_usd : firstDaily.price_usd}
              label={isToday ? formatTime(intradayRows[0].observation_timestamp) : formatDate(firstDaily.snapshot_date)}
              observationCount={observationCount}
              note={isToday ? t("coinDetails.insufficientHistory.intradayNote") : undefined}
            />
          ) : (
            <>
              <dl className="overview-grid coin-details__summary-grid">
                <div className="overview-card">
                  <dt>{t("coinDetails.periodMin")}</dt>
                  <dd>{formatCryptoPrice(periodSummary?.minPrice)}</dd>
                </div>
                <div className="overview-card">
                  <dt>{t("coinDetails.periodMax")}</dt>
                  <dd>{formatCryptoPrice(periodSummary?.maxPrice)}</dd>
                </div>
                <div className="overview-card">
                  <dt>{t("coinDetails.periodAverage")}</dt>
                  <dd>{formatCryptoPrice(periodSummary?.avgPrice)}</dd>
                </div>
                <div className="overview-card">
                  <dt>{t("coinDetails.observations")}</dt>
                  <dd>{formatNumber(observationCount)}</dd>
                </div>
                <div className="overview-card">
                  <dt>{isToday ? t("coinDetails.firstObservation") : t("coinDetails.firstSnapshot")}</dt>
                  <dd>{periodSummary?.firstLabel}</dd>
                </div>
                <div className="overview-card">
                  <dt>{isToday ? t("coinDetails.latestObservation") : t("coinDetails.latestSnapshot")}</dt>
                  <dd>{periodSummary?.latestLabel}</dd>
                </div>
              </dl>

              <div className="coin-details__charts">
                <MetricChart
                  title={t("coinDetails.priceChartTitle")}
                  subtitle={priceSubtitle}
                  data={priceData}
                  color="#6d28d9"
                  variant="area"
                  axisFormatter={formatCompactUsd}
                  tooltipFormatter={formatCryptoPrice}
                  xAxisFormatter={isToday ? formatTime : undefined}
                  xLabelFormatter={isToday ? formatTime : undefined}
                />
                <MetricChart
                  title={t("coinDetails.volumeChartTitle")}
                  subtitle={isToday ? t("coinDetails.volumeChartIntradaySubtitle") : undefined}
                  data={volumeData}
                  color="#ea580c"
                  axisFormatter={formatCompactUsd}
                  tooltipFormatter={formatCompactUsd}
                  xAxisFormatter={isToday ? formatTime : undefined}
                  xLabelFormatter={isToday ? formatTime : undefined}
                />
              </div>
            </>
          )}
        </>
      )}

      {symbol && <AICoinAnalysisCard symbol={symbol} />}
    </main>
  );
}
