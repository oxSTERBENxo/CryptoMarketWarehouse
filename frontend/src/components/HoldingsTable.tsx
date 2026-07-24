import { useTranslation } from "react-i18next";
import type { Holding } from "../api/types";
import { formatCryptoPrice, formatSignedPercent, formatSignedUsd, formatUsd } from "../utils/format";
import { CoinLogo } from "./CoinLogo";
import { PercentChangeBadge } from "./PercentChangeBadge";
import "./Table.css";
import "./PortfolioSummaryCards.css";
import "./Modal.css";
import "./HoldingsTable.css";

interface HoldingsTableProps {
  holdings: Holding[];
  onEdit: (holding: Holding) => void;
  onDelete: (holding: Holding) => void;
}

function formatQuantity(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 8 });
}

function profitClass(value: number | null): string {
  if (value === null || value === 0) return "profit-neutral";
  return value > 0 ? "profit-positive" : "profit-negative";
}

export function HoldingsTable({ holdings, onEdit, onDelete }: HoldingsTableProps) {
  const { t } = useTranslation();
  return (
    <div className="table-scroll">
      <table>
        <caption className="sr-only">{t("portfolio.holdingsTable.caption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("table.coin")}</th>
            <th scope="col">{t("portfolio.holdingsTable.quantity")}</th>
            <th scope="col">{t("portfolio.holdingsTable.averageBuyPrice")}</th>
            <th scope="col">{t("portfolio.holdingsTable.currentPrice")}</th>
            <th scope="col">{t("table.change24h")}</th>
            <th scope="col">{t("portfolio.holdingsTable.currentValue")}</th>
            <th scope="col">{t("portfolio.holdingsTable.profitLoss")}</th>
            <th scope="col">{t("portfolio.summary.profitPercent")}</th>
            <th scope="col">
              <span className="sr-only">{t("portfolio.holdingsTable.actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding) => (
            <tr key={holding.id}>
              <td>
                <span className="table-cell--coin">
                  <CoinLogo src={holding.image_url} name={holding.coin_name ?? holding.coin_symbol} />
                  {holding.coin_name ?? holding.coin_symbol}{" "}
                  <span className="symbol-cell">({holding.coin_symbol})</span>
                </span>
              </td>
              <td>{formatQuantity(holding.quantity)}</td>
              <td>{formatCryptoPrice(holding.average_buy_price)}</td>
              <td>
                {holding.current_price === null
                  ? t("portfolio.holdingsTable.priceUnavailable")
                  : formatCryptoPrice(holding.current_price)}
              </td>
              <td>
                <PercentChangeBadge value={holding.price_change_percentage_24h} />
              </td>
              <td>{holding.current_value === null ? "—" : formatUsd(holding.current_value)}</td>
              <td className={profitClass(holding.unrealized_profit)}>{formatSignedUsd(holding.unrealized_profit)}</td>
              <td className={profitClass(holding.profit_percent)}>{formatSignedPercent(holding.profit_percent)}</td>
              <td>
                <div className="holdings-table__actions">
                  <button type="button" className="modal-button" onClick={() => onEdit(holding)}>
                    {t("common.edit")}
                  </button>
                  <button type="button" className="modal-button" onClick={() => onDelete(holding)}>
                    {t("common.delete")}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
