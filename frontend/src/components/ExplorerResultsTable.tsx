import { useNavigate } from "react-router-dom";
import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import type { ExplorerResultRow, ExplorerSortField, SortOrder } from "../api/types";
import { CoinLogo } from "./CoinLogo";
import { PercentChangeBadge } from "./PercentChangeBadge";
import {
  changeClass,
  formatCompactUsd,
  formatCryptoPrice,
  formatNumber,
  formatRank,
  formatSignedUsd,
} from "../utils/format";
import "./Table.css";
import "./ExplorerResultsTable.css";

interface ExplorerResultsTableProps {
  rows: ExplorerResultRow[];
  sortBy: ExplorerSortField;
  sortOrder: SortOrder;
  /** Header click: re-sorts server-side (same field toggles direction). */
  onSortChange: (field: ExplorerSortField) => void;
  offset: number;
  limit: number;
  totalResults: number;
  onPageChange: (offset: number) => void;
  /** Carried into Coin Details via ?from/&to so its chart opens on the analyzed range. */
  fromDate: string;
  toDate: string;
}

const COLUMNS: { field: ExplorerSortField | null; labelKey: string }[] = [
  { field: null, labelKey: "explorer.columns.coin" },
  { field: null, labelKey: "explorer.columns.startPrice" },
  { field: "end_price", labelKey: "explorer.columns.endPrice" },
  { field: "dollar_change", labelKey: "explorer.columns.dollarChange" },
  { field: "percent_change", labelKey: "explorer.columns.percentChange" },
  { field: "avg_volume", labelKey: "explorer.columns.avgVolume" },
  { field: null, labelKey: "explorer.columns.startRank" },
  { field: null, labelKey: "explorer.columns.endRank" },
  { field: "rank_change", labelKey: "explorer.columns.rankChange" },
  { field: "volatility", labelKey: "explorer.columns.volatility" },
  { field: "market_cap", labelKey: "explorer.columns.marketCap" },
];

function Row({ row, fromDate, toDate }: { row: ExplorerResultRow; fromDate: string; toDate: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const to = `/coins/${row.symbol.toLowerCase()}?from=${fromDate}&to=${toDate}`;
  const open = () => navigate(to);
  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      open();
    }
  };
  return (
    <tr
      className="table-row--clickable"
      onClick={open}
      onKeyDown={onKeyDown}
      tabIndex={0}
      role="link"
      aria-label={t("explorer.results.openDetails", { name: row.name })}
    >
      <td>
        <span className="table-cell--coin">
          <CoinLogo src={row.image_url} name={row.name} />
          {row.name} <span className="symbol-cell">{row.symbol.toUpperCase()}</span>
        </span>
      </td>
      <td>{formatCryptoPrice(row.start_price)}</td>
      <td>{formatCryptoPrice(row.end_price)}</td>
      <td className={changeClass(row.dollar_change)}>{formatSignedUsd(row.dollar_change)}</td>
      <td>
        <PercentChangeBadge value={row.percent_change} />
      </td>
      <td>{formatCompactUsd(row.avg_volume)}</td>
      <td>{formatRank(row.start_rank)}</td>
      <td>{formatRank(row.end_rank)}</td>
      <td className={changeClass(row.rank_change)}>
        {row.rank_change === null ? "—" : `${row.rank_change > 0 ? "+" : ""}${formatNumber(row.rank_change)}`}
      </td>
      <td>{row.volatility_percent === null ? "—" : `${row.volatility_percent.toFixed(2)}%`}</td>
      <td>{formatCompactUsd(row.market_cap_usd)}</td>
    </tr>
  );
}

export function ExplorerResultsTable({
  rows,
  sortBy,
  sortOrder,
  onSortChange,
  offset,
  limit,
  totalResults,
  onPageChange,
  fromDate,
  toDate,
}: ExplorerResultsTableProps) {
  const { t } = useTranslation();
  const pageStart = totalResults === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + limit, totalResults);
  const hasPrev = offset > 0;
  const hasNext = offset + limit < totalResults;

  return (
    <section aria-labelledby="explorer-results-heading" className="table-section">
      <h2 id="explorer-results-heading" className="sr-only">
        {t("explorer.results.heading")}
      </h2>
      <div className="table-scroll explorer-table-scroll">
        <table>
          <caption className="sr-only">{t("explorer.results.caption")}</caption>
          <thead>
            <tr>
              {COLUMNS.map((column) =>
                column.field ? (
                  <th key={column.labelKey} scope="col" aria-sort={sortBy === column.field ? (sortOrder === "asc" ? "ascending" : "descending") : undefined}>
                    <button
                      type="button"
                      className="explorer-sort-header"
                      data-active={sortBy === column.field}
                      onClick={() => onSortChange(column.field!)}
                    >
                      {t(column.labelKey)}
                      {sortBy === column.field && <span aria-hidden>{sortOrder === "asc" ? " ▲" : " ▼"}</span>}
                    </button>
                  </th>
                ) : (
                  <th key={column.labelKey} scope="col">
                    {t(column.labelKey)}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <Row key={row.coin_id} row={row} fromDate={fromDate} toDate={toDate} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="explorer-pagination">
        <span className="explorer-pagination__info">
          {t("explorer.results.showing", {
            start: formatNumber(pageStart),
            end: formatNumber(pageEnd),
            total: formatNumber(totalResults),
          })}
        </span>
        <div className="explorer-pagination__buttons">
          <button
            type="button"
            className="explorer-pagination__button"
            disabled={!hasPrev}
            onClick={() => onPageChange(Math.max(0, offset - limit))}
          >
            {t("explorer.results.previous")}
          </button>
          <button
            type="button"
            className="explorer-pagination__button"
            disabled={!hasNext}
            onClick={() => onPageChange(offset + limit)}
          >
            {t("explorer.results.next")}
          </button>
        </div>
      </div>
    </section>
  );
}
