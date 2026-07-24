import { useId } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatChartAxisDate, formatDate } from "../utils/format";
import { EmptyState } from "./EmptyState";
import "./MetricChart.css";

export interface MetricChartPoint {
  date: string;
  value: number | null;
}

interface MetricChartProps {
  title: string;
  /** Optional line under the title, e.g. "+12.4% over 30 days". */
  subtitle?: string;
  data: MetricChartPoint[];
  color: string;
  axisFormatter: (value: number) => string;
  tooltipFormatter: (value: number) => string;
  /** Reverses the Y axis so a lower value (e.g. market-cap rank 1) plots higher — better is up. */
  reversed?: boolean;
  allowDecimals?: boolean;
  /** "area" renders a subtle gradient fill under the line; "line" (default) is a plain line. */
  variant?: "line" | "area";
  /** X-axis tick formatter. Defaults to day-level date labels ("Jul 22"); intraday callers pass
   * hour:minute labels ("09:00") instead. */
  xAxisFormatter?: (value: string) => string;
  /** Tooltip label (header) formatter for each point's `date`/timestamp. Defaults to a full date. */
  xLabelFormatter?: (value: string) => string;
  /** Minimum non-null observations required to plot a trend line (default 2 -- a single point
   * can't show a trend). Below this, the compact empty-state message renders instead of a chart. */
  minValidPoints?: number;
  /** Message shown when fewer than `minValidPoints` valid observations exist. */
  insufficientMessage?: string;
}

/** One metric plotted over time. Renders an empty message instead of an empty/broken chart canvas. */
export function MetricChart({
  title,
  subtitle,
  data,
  color,
  axisFormatter,
  tooltipFormatter,
  reversed = false,
  allowDecimals = true,
  variant = "line",
  xAxisFormatter = formatChartAxisDate,
  xLabelFormatter = formatDate,
  minValidPoints = 2,
  insufficientMessage,
}: MetricChartProps) {
  const { t } = useTranslation();
  const headingId = useId();
  const gradientId = useId();
  const validCount = data.reduce((count, point) => (point.value != null ? count + 1 : count), 0);
  const hasData = validCount >= minValidPoints;

  const tooltipProps = {
    labelFormatter: (label: ReactNode) => xLabelFormatter(String(label)),
    formatter: (value: unknown) => [tooltipFormatter(Number(value)), title] as [string, string],
    contentStyle: {
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: 8,
      boxShadow: "var(--shadow)",
      color: "var(--text-h)",
      fontSize: 13,
    },
    labelStyle: { color: "var(--text)", marginBottom: 4 },
    cursor: { stroke: "var(--border)", strokeWidth: 1 },
  };

  const axisProps = {
    stroke: "var(--text)",
    fontSize: 12,
  };

  return (
    <section aria-labelledby={headingId} className="table-section metric-chart-section">
      <div className="metric-chart-heading">
        <h2 id={headingId}>{title}</h2>
        <p className="metric-chart-subtitle" aria-hidden={!subtitle}>
          {subtitle ?? " "}
        </p>
      </div>
      {hasData ? (
        <div className="chart-card" role="img" aria-label={t("chart.overTime", { title })}>
          <ResponsiveContainer width="100%" height={260}>
            {variant === "area" ? (
              <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={color} stopOpacity={0.35} />
                    <stop offset="95%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(value: string) => xAxisFormatter(value)}
                  minTickGap={24}
                  {...axisProps}
                />
                <YAxis
                  tickFormatter={(value: number) => axisFormatter(value)}
                  width={72}
                  domain={["auto", "auto"]}
                  {...axisProps}
                />
                <Tooltip {...tooltipProps} />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke={color}
                  strokeWidth={2}
                  fill={`url(#${gradientId})`}
                  connectNulls={false}
                  isAnimationActive={false}
                  dot={{ r: 3, strokeWidth: 0, fill: color }}
                  activeDot={{ r: 5, strokeWidth: 0, fill: color }}
                />
              </AreaChart>
            ) : (
              <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(value: string) => xAxisFormatter(value)}
                  minTickGap={24}
                  {...axisProps}
                />
                <YAxis
                  tickFormatter={(value: number) => axisFormatter(value)}
                  width={72}
                  reversed={reversed}
                  allowDecimals={allowDecimals}
                  domain={reversed ? [1, "dataMax"] : ["auto", "auto"]}
                  {...axisProps}
                />
                <Tooltip {...tooltipProps} />
                <Line
                  type="linear"
                  dataKey="value"
                  stroke={color}
                  strokeWidth={2}
                  dot={{ r: 3, strokeWidth: 0, fill: color }}
                  activeDot={{ r: 5, strokeWidth: 0, fill: color }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      ) : (
        <EmptyState message={insufficientMessage ?? t("chart.insufficientData")} />
      )}
    </section>
  );
}
