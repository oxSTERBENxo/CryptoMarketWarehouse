import { useId } from "react";
import { useTranslation } from "react-i18next";
import type { MarketMoverEntry } from "../api/types";
import { CoinLogo } from "./CoinLogo";
import { useRowNavigate } from "../hooks/useRowNavigate";
import { formatSignedPercent } from "../utils/format";
import "./PortfolioSummaryCards.css";
import "./MarketMoverList.css";

interface MarketMoverListProps {
  title: string;
  icon: string;
  entries: MarketMoverEntry[];
  direction: "gain" | "loss";
}

function rowArrow(percentChange: number | null): string {
  if (percentChange === null || percentChange === 0) return "•";
  return percentChange > 0 ? "▲" : "▼";
}

function rowChangeClass(percentChange: number | null): string {
  if (percentChange === null || percentChange === 0) return "profit-neutral";
  return percentChange > 0 ? "profit-positive" : "profit-negative";
}

/** One "Top Gainers" / "Biggest Losers" card: a ranked list of coins with their signed percent
 * change for the currently selected Market Leaders period. Each row's arrow/color reflects that
 * row's own sign (not just the card's direction) -- when a period has fewer real decliners than
 * the requested limit, the "losers" list pads out with the smallest gainers, and those rows must
 * still read as gains, not be painted red. */
export function MarketMoverList({ title, icon, entries, direction }: MarketMoverListProps) {
  const { t } = useTranslation();
  const headingId = useId();

  return (
    <section aria-labelledby={headingId} className={`mover-list mover-list--${direction}`}>
      <h2 id={headingId} className="mover-list__heading">
        <span aria-hidden="true">{icon}</span> {title}
      </h2>
      {entries.length === 0 ? (
        <p className="mover-list__empty">{t("marketLeaders.noDataForPeriodShort")}</p>
      ) : (
        <ol className="mover-list__items">
          {entries.map((entry, index) => (
            <MoverRow key={entry.coin_id} entry={entry} index={index} />
          ))}
        </ol>
      )}
    </section>
  );
}

function MoverRow({ entry, index }: { entry: MarketMoverEntry; index: number }) {
  const { t } = useTranslation();
  const rowProps = useRowNavigate(entry.symbol, t("common.openDetails", { name: entry.name }));
  return (
    <li className="mover-list__item mover-list__item--clickable" {...rowProps}>
      <span className="mover-list__rank">{index + 1}</span>
      <CoinLogo src={entry.image_url} name={entry.name} size={24} />
      <span className="mover-list__identity">
        <span className="mover-list__name">{entry.name}</span>
        <span className="mover-list__symbol">{entry.symbol.toUpperCase()}</span>
      </span>
      <span className={`mover-list__change ${rowChangeClass(entry.percent_change)}`}>
        <span aria-hidden="true">{rowArrow(entry.percent_change)}</span> {formatSignedPercent(entry.percent_change)}
      </span>
    </li>
  );
}
