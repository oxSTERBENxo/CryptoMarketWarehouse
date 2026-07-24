import { useTranslation } from "react-i18next";
import type { CurrentMarketCoin } from "../api/types";
import { formatCompactUsd, formatCryptoPrice } from "../utils/format";
import { SectionStatus } from "./SectionStatus";
import { CoinLogo } from "./CoinLogo";
import { PercentChangeBadge } from "./PercentChangeBadge";
import { useRowNavigate } from "../hooks/useRowNavigate";
import "./Table.css";

interface TopVolumeTableProps {
  entries: CurrentMarketCoin[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

function Row({ entry, index }: { entry: CurrentMarketCoin; index: number }) {
  const { t } = useTranslation();
  const rowProps = useRowNavigate(entry.symbol, t("common.openDetails", { name: entry.name }));
  return (
    <tr className="table-row--clickable" {...rowProps}>
      <td>{index + 1}</td>
      <td>
        <span className="table-cell--coin">
          <CoinLogo src={entry.image_url} name={entry.name} />
          {entry.name}
        </span>
      </td>
      <td className="symbol-cell">{entry.symbol.toUpperCase()}</td>
      <td>{formatCryptoPrice(entry.price_usd)}</td>
      <td>
        <PercentChangeBadge value={entry.price_change_percentage_24h} />
      </td>
      <td>{formatCompactUsd(entry.volume_24h_usd)}</td>
      <td>{formatCompactUsd(entry.market_cap_usd)}</td>
    </tr>
  );
}

export function TopVolumeTable({ entries, loading, error, onRetry }: TopVolumeTableProps) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="top-volume-heading" className="table-section">
      <h2 id="top-volume-heading">{t("dashboard.topVolume.title")}</h2>
      <SectionStatus loading={loading} error={error} isEmpty={!entries || entries.length === 0} onRetry={onRetry}>
        <div className="table-scroll">
          <table>
            <caption className="sr-only">{t("dashboard.topVolume.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">{t("table.coin")}</th>
                <th scope="col">{t("table.symbol")}</th>
                <th scope="col">{t("table.price")}</th>
                <th scope="col">{t("table.change24h")}</th>
                <th scope="col">{t("table.volume24h")}</th>
                <th scope="col">{t("table.marketCap")}</th>
              </tr>
            </thead>
            <tbody>
              {entries?.map((entry, index) => (
                <Row key={entry.coin_id} entry={entry} index={index} />
              ))}
            </tbody>
          </table>
        </div>
      </SectionStatus>
    </section>
  );
}
