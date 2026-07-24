import { useTranslation } from "react-i18next";
import type { MarketLeadersCoverage } from "../api/types";
import { formatIsoDate } from "../utils/format";
import "./CoverageBar.css";

interface CoverageBarProps {
  coverage: MarketLeadersCoverage;
  periodLabel: string;
}

/** Part 6 of the Market Leaders fix: always show what data actually backs the selected period --
 * how many coins qualified and the real earliest/latest observation -- so an empty leaderboard
 * reads as "here's exactly why" instead of a bare "no data". Renders even when there's an
 * observed range but zero qualifying coins, and even when there's no observed range at all. */
export function CoverageBar({ coverage, periodLabel }: CoverageBarProps) {
  const { t } = useTranslation();
  const hasRange = coverage.earliest_observation !== null && coverage.latest_observation !== null;

  return (
    <div className="coverage-bar">
      <span className="coverage-bar__count">
        {periodLabel} · {t("coverageBar.qualifyingCoins", { count: coverage.qualifying_coin_count })}
      </span>
      {hasRange && (
        <span className="coverage-bar__range">
          {formatIsoDate(coverage.earliest_observation)} – {formatIsoDate(coverage.latest_observation)}
        </span>
      )}
    </div>
  );
}
