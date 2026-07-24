import { useTranslation } from "react-i18next";
import type { CurrentMarketCoin } from "../api/types";
import { formatCompactUsd, formatCryptoPrice, formatNumber } from "../utils/format";
import { SectionStatus } from "./SectionStatus";
import { CoinLogo } from "./CoinLogo";
import { PercentChangeBadge } from "./PercentChangeBadge";
import { useRowNavigate } from "../hooks/useRowNavigate";
import "./Table.css";

interface LatestSnapshotTableProps {
  snapshots: CurrentMarketCoin[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

function Row({ snapshot }: { snapshot: CurrentMarketCoin }) {
  const { t } = useTranslation();
  const rowProps = useRowNavigate(snapshot.symbol, t("common.openDetails", { name: snapshot.name }));
  return (
    <tr className="table-row--clickable" {...rowProps}>
      <td>
        <span className="table-cell--coin">
          <CoinLogo src={snapshot.image_url} name={snapshot.name} />
          {snapshot.name}
        </span>
      </td>
      <td className="symbol-cell">{snapshot.symbol.toUpperCase()}</td>
      <td>{formatCryptoPrice(snapshot.price_usd)}</td>
      <td>
        <PercentChangeBadge value={snapshot.price_change_percentage_24h} />
      </td>
      <td>{formatCompactUsd(snapshot.market_cap_usd)}</td>
      <td>{formatCompactUsd(snapshot.volume_24h_usd)}</td>
      <td>{snapshot.market_cap_rank != null ? formatNumber(snapshot.market_cap_rank) : "—"}</td>
    </tr>
  );
}

export function LatestSnapshotTable({ snapshots, loading, error, onRetry }: LatestSnapshotTableProps) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="latest-snapshot-heading" className="table-section">
      <h2 id="latest-snapshot-heading">{t("dashboard.latestSnapshot.title")}</h2>
      <SectionStatus loading={loading} error={error} isEmpty={!snapshots || snapshots.length === 0} onRetry={onRetry}>
        <div className="table-scroll">
          <table>
            <caption className="sr-only">{t("dashboard.latestSnapshot.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("table.coin")}</th>
                <th scope="col">{t("table.symbol")}</th>
                <th scope="col">{t("table.price")}</th>
                <th scope="col">{t("table.change24h")}</th>
                <th scope="col">{t("table.marketCap")}</th>
                <th scope="col">{t("table.volume24h")}</th>
                <th scope="col">{t("table.rank")}</th>
              </tr>
            </thead>
            <tbody>
              {snapshots?.map((snapshot) => (
                <Row key={snapshot.coin_id} snapshot={snapshot} />
              ))}
            </tbody>
          </table>
        </div>
      </SectionStatus>
    </section>
  );
}
