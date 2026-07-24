import { useState } from "react";
import { useTranslation } from "react-i18next";
import { getMarketLeaders } from "../api/analytics";
import { useApiData } from "../hooks/useApiData";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { RangeSelector } from "../components/RangeSelector";
import { RefreshMarketDataButton } from "../components/RefreshMarketDataButton";
import { MarketLeadersSummaryBar } from "../components/MarketLeadersSummaryBar";
import { HighlightCards } from "../components/HighlightCards";
import { MarketMoverList } from "../components/MarketMoverList";
import { CoverageBar } from "../components/CoverageBar";
import { DEFAULT_LEADERS_RANGE, LEADERS_RANGE_OPTIONS } from "../utils/dateRange";
import type { LeadersRangeOption } from "../utils/dateRange";
import "./MarketLeaders.css";

const MOVERS_LIMIT = 5;

const PERIOD_LABEL_KEYS: Record<LeadersRangeOption, string> = {
  today: "marketLeaders.periodLong.today",
  "7d": "marketLeaders.periodLong.7d",
  "30d": "marketLeaders.periodLong.30d",
  "90d": "marketLeaders.periodLong.90d",
  "1y": "marketLeaders.periodLong.1y",
};

const SHORT_PERIOD_LABELS: Record<LeadersRangeOption, string> = {
  today: "Today",
  "7d": "7D",
  "30d": "30D",
  "90d": "90D",
  "1y": "1Y",
};

export function MarketLeaders() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<LeadersRangeOption>(DEFAULT_LEADERS_RANGE);
  const leaders = useApiData(() => getMarketLeaders(period, MOVERS_LIMIT), [period]);
  const data = leaders.data;
  const hasMovers = !!data && (data.gainers.length > 0 || data.losers.length > 0);
  const shortPeriodLabel = period === "today" ? t("dateRange.today") : SHORT_PERIOD_LABELS[period];

  return (
    <main className="market-leaders">
      <div className="market-leaders__header">
        <div>
          <h1 className="market-leaders__title">{t("marketLeaders.title")}</h1>
          <p className="market-leaders__subtitle">{t("marketLeaders.subtitle")}</p>
        </div>
        <RefreshMarketDataButton onRefreshed={leaders.retry} />
      </div>

      <div className="market-leaders__range-row">
        <RangeSelector value={period} onChange={setPeriod} options={LEADERS_RANGE_OPTIONS} />
      </div>

      {leaders.loading && <LoadingState label={t("marketLeaders.loading")} />}
      {!leaders.loading && leaders.error && <ErrorState message={leaders.error} onRetry={leaders.retry} />}

      {!leaders.loading && !leaders.error && data && (
        <>
          <CoverageBar coverage={data.coverage} periodLabel={shortPeriodLabel} />

          <MarketLeadersSummaryBar summary={data.summary} />

          <HighlightCards
            topGainer={data.gainers[0] ?? null}
            topLoser={data.losers[0] ?? null}
            highestVolume={data.highest_volume}
            highestRanked={data.highest_ranked}
            mostVolatile={data.most_volatile}
            periodLabel={t(PERIOD_LABEL_KEYS[period])}
          />

          {hasMovers ? (
            <div className="market-leaders__lists">
              <MarketMoverList title={t("marketLeaders.topGainers")} icon="🚀" entries={data.gainers} direction="gain" />
              <MarketMoverList title={t("marketLeaders.biggestLosers")} icon="📉" entries={data.losers} direction="loss" />
            </div>
          ) : (
            <EmptyState
              message={
                data.coverage.empty_reason ??
                (period === "today" ? t("marketLeaders.emptyToday") : t("marketLeaders.emptyOther"))
              }
            />
          )}
        </>
      )}
    </main>
  );
}
