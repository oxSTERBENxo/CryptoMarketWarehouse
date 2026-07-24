import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { getCurrentMarket, getOverview } from "../api/analytics";
import { useApiData } from "../hooks/useApiData";
import { AIMarketSummaryCard } from "../components/AIMarketSummaryCard";
import { OverviewCards } from "../components/OverviewCards";
import { SchedulerStatusCard } from "../components/SchedulerStatusCard";
import { TakeSnapshotButton } from "../components/TakeSnapshotButton";
import { RecoveryStatusBanner } from "../components/RecoveryStatusBanner";
import { TopMarketCapTable } from "../components/TopMarketCapTable";
import { TopVolumeTable } from "../components/TopVolumeTable";
import { LatestSnapshotTable } from "../components/LatestSnapshotTable";
import type { CurrentMarketCoin } from "../api/types";
import "./Dashboard.css";

const LATEST_DISPLAY_LIMIT = 10;
const TOP_MARKET_CAP_LIMIT = 10;
const TOP_VOLUME_LIMIT = 10;

function topBy(coins: CurrentMarketCoin[], key: "market_cap_usd" | "volume_24h_usd", limit: number): CurrentMarketCoin[] {
  return [...coins]
    .sort((a, b) => (b[key] ?? -Infinity) - (a[key] ?? -Infinity))
    .slice(0, limit);
}

export function Dashboard() {
  const { t } = useTranslation();
  // Daily warehouse-load timestamp for the Data Collection card only -- distinct from `current`
  // below, which is live and updates on every Take New Snapshot press regardless of whether a
  // new daily row landed.
  const overview = useApiData(getOverview);
  const current = useApiData(() => getCurrentMarket());

  const coins = current.data?.coins ?? null;
  const topMarketCap = useMemo(() => (coins ? topBy(coins, "market_cap_usd", TOP_MARKET_CAP_LIMIT) : null), [coins]);
  const topVolume = useMemo(() => (coins ? topBy(coins, "volume_24h_usd", TOP_VOLUME_LIMIT) : null), [coins]);
  const latestForDisplay = useMemo(
    () => (coins ? topBy(coins, "market_cap_usd", LATEST_DISPLAY_LIMIT) : null),
    [coins]
  );

  return (
    <main className="dashboard">
      <RecoveryStatusBanner />

      <div className="dashboard-header">
        <h1 className="dashboard-title">{t("nav.dashboard")}</h1>
        <TakeSnapshotButton
          onRefreshed={() => {
            current.retry();
            overview.retry();
          }}
          lastRefreshedAt={current.data?.refreshed_at}
          latestDailySnapshotDate={overview.data?.snapshot_date}
        />
      </div>

      <AIMarketSummaryCard />

      <SchedulerStatusCard latestSnapshotDate={overview.data?.snapshot_date} />

      <OverviewCards
        overview={current.data}
        loading={current.loading}
        error={current.error}
        onRetry={current.retry}
      />

      <TopMarketCapTable
        entries={topMarketCap}
        loading={current.loading}
        error={current.error}
        onRetry={current.retry}
      />

      <TopVolumeTable entries={topVolume} loading={current.loading} error={current.error} onRetry={current.retry} />

      <LatestSnapshotTable
        snapshots={latestForDisplay}
        loading={current.loading}
        error={current.error}
        onRetry={current.retry}
      />
    </main>
  );
}
