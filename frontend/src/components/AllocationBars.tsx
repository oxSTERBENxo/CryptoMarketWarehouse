import { useTranslation } from "react-i18next";
import type { PaperHolding } from "../api/types";
import { formatUsd } from "../utils/format";
import "./AllocationBars.css";

interface AllocationBarsProps {
  holdings: PaperHolding[];
  cashBalance: number;
  totalEquity: number;
}

const BAR_COLORS = ["#6d28d9", "#0891b2", "#ea580c", "#059669", "#d97706", "#db2777", "#4f46e5"];

/** Proportional allocation bars (cash + each holding) — a dependency-free stand-in for a donut
 * chart, per the spec allowing either. */
export function AllocationBars({ holdings, cashBalance, totalEquity }: AllocationBarsProps) {
  const { t } = useTranslation();
  const cashPercent = totalEquity > 0 ? (cashBalance / totalEquity) * 100 : 0;

  const rows = [
    { label: t("portfolio.paper.cash"), percent: cashPercent, value: cashBalance, color: "var(--border)" },
    ...holdings
      .filter((h) => h.current_value !== null)
      .map((h, index) => ({
        label: h.coin_symbol,
        percent: h.allocation_percent ?? 0,
        value: h.current_value ?? 0,
        color: BAR_COLORS[index % BAR_COLORS.length],
      })),
  ];

  return (
    <div className="allocation-bars">
      {rows.map((row) => (
        <div className="allocation-bars__row" key={row.label}>
          <div className="allocation-bars__label">
            <span>{row.label}</span>
            <span>
              {formatUsd(row.value)} · {row.percent.toFixed(1)}%
            </span>
          </div>
          <div className="allocation-bars__track">
            <div
              className="allocation-bars__fill"
              style={{ width: `${Math.min(row.percent, 100)}%`, background: row.color }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
