import { useTranslation } from "react-i18next";
import type { PaperTransaction } from "../api/types";
import { formatCryptoPrice, formatDateTime, formatSignedUsd, formatUsd } from "../utils/format";
import "./Table.css";

interface PaperTransactionsTableProps {
  transactions: PaperTransaction[];
}

function formatQuantity(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 8 });
}

function profitClass(value: number | null): string {
  if (value === null || value === 0) return "profit-neutral";
  return value > 0 ? "profit-positive" : "profit-negative";
}

export function PaperTransactionsTable({ transactions }: PaperTransactionsTableProps) {
  const { t } = useTranslation();
  return (
    <div className="table-scroll">
      <table>
        <caption className="sr-only">{t("portfolio.paper.transactionsCaption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("portfolio.paper.time")}</th>
            <th scope="col">{t("portfolio.paper.type")}</th>
            <th scope="col">{t("table.coin")}</th>
            <th scope="col">{t("portfolio.holdingsTable.quantity")}</th>
            <th scope="col">{t("portfolio.paper.executionPrice")}</th>
            <th scope="col">{t("portfolio.paper.totalValue")}</th>
            <th scope="col">{t("portfolio.paper.realizedPl")}</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) => (
            <tr key={tx.id}>
              <td>{formatDateTime(tx.executed_at)}</td>
              <td>
                <span className={tx.transaction_type === "BUY" ? "profit-positive" : "profit-negative"}>
                  {tx.transaction_type === "BUY" ? t("portfolio.paper.buy") : t("portfolio.paper.sell")}
                </span>
              </td>
              <td className="symbol-cell">{tx.coin_symbol}</td>
              <td>{formatQuantity(tx.quantity)}</td>
              <td>{formatCryptoPrice(tx.execution_price)}</td>
              <td>{formatUsd(tx.total_value)}</td>
              <td className={profitClass(tx.realized_profit)}>
                {tx.realized_profit === null ? "—" : formatSignedUsd(tx.realized_profit)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
