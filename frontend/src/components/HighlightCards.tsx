import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { MarketMoverEntry } from "../api/types";
import { CoinLink } from "./CoinLink";
import { CoinLogo } from "./CoinLogo";
import { formatCompactUsd, formatRank, formatSignedPercent } from "../utils/format";
import "./HighlightCards.css";

interface HighlightCardsProps {
  topGainer: MarketMoverEntry | null;
  topLoser: MarketMoverEntry | null;
  highestVolume: MarketMoverEntry | null;
  highestRanked: MarketMoverEntry | null;
  mostVolatile: MarketMoverEntry | null;
  periodLabel: string;
}

interface HeroCardProps {
  icon: string;
  label: string;
  entry: MarketMoverEntry | null;
  periodLabel: string;
}

/** A hero card's accent (color/arrow/gradient) always reflects the actual sign of its entry's
 * percent_change, not just which slot ("Highest Gainer" vs "Largest Loser") it's rendered in --
 * on an all-red day, the period's best performer can still be negative, and must read as a loss,
 * not be painted green just because it's technically the "highest" of the bunch. */
function HeroCard({ icon, label, entry, periodLabel }: HeroCardProps) {
  const { t } = useTranslation();
  const isNegative = entry != null && entry.percent_change != null && entry.percent_change < 0;
  const sign = isNegative ? "loss" : "gain";
  const arrow = isNegative ? "▼" : "▲";
  return (
    <article className={`highlight-hero highlight-hero--${sign}`}>
      <div className="highlight-hero__label">
        <span aria-hidden="true">{icon}</span> {label}
      </div>
      {entry ? (
        <>
          <CoinLink symbol={entry.symbol}>
            <span className="highlight-hero__coin">
              <CoinLogo src={entry.image_url} name={entry.name} size={22} /> {entry.name}
            </span>
          </CoinLink>
          <div className="highlight-hero__value">
            <span aria-hidden="true">{arrow}</span>
            {formatSignedPercent(entry.percent_change)}
          </div>
          <p className="highlight-hero__subtitle">{t("marketLeaders.over", { period: periodLabel })}</p>
        </>
      ) : (
        <p className="highlight-hero__empty">{t("marketLeaders.noDataForPeriod")}</p>
      )}
    </article>
  );
}

interface StatCardProps {
  icon: string;
  label: string;
  entry: MarketMoverEntry | null;
  value: (entry: MarketMoverEntry) => ReactNode;
  subtitle: (entry: MarketMoverEntry) => string;
}

function StatCard({ icon, label, entry, value, subtitle }: StatCardProps) {
  const { t } = useTranslation();
  return (
    <article className="highlight-stat">
      <div className="highlight-stat__label">
        <span aria-hidden="true">{icon}</span> {label}
      </div>
      {entry ? (
        <>
          <CoinLink symbol={entry.symbol}>
            <span className="highlight-stat__coin">
              <CoinLogo src={entry.image_url} name={entry.name} size={20} /> {entry.name}
            </span>
          </CoinLink>
          <div className="highlight-stat__value">{value(entry)}</div>
          <p className="highlight-stat__subtitle">{subtitle(entry)}</p>
        </>
      ) : (
        <p className="highlight-stat__empty">{t("marketLeaders.noData")}</p>
      )}
    </article>
  );
}

/** The Market Leaders "premium" highlight row: the period's best/worst performer as large hero
 * cards, plus three supporting stat cards (highest volume, highest rank, most volatile). */
export function HighlightCards({
  topGainer,
  topLoser,
  highestVolume,
  highestRanked,
  mostVolatile,
  periodLabel,
}: HighlightCardsProps) {
  const { t } = useTranslation();
  return (
    <div className="highlight-cards">
      <HeroCard icon="🚀" label={t("marketLeaders.highestGainer")} entry={topGainer} periodLabel={periodLabel} />
      <HeroCard icon="📉" label={t("marketLeaders.largestLoser")} entry={topLoser} periodLabel={periodLabel} />
      <StatCard
        icon="💰"
        label={t("marketLeaders.highestVolume")}
        entry={highestVolume}
        value={(e) => formatCompactUsd(e.volume_24h_usd)}
        subtitle={() => t("marketLeaders.volume24hSubtitle")}
      />
      <StatCard
        icon="👑"
        label={t("marketLeaders.highestRanked")}
        entry={highestRanked}
        value={(e) => formatRank(e.market_cap_rank)}
        subtitle={() => t("marketLeaders.byMarketCap")}
      />
      <StatCard
        icon="⚡"
        label={t("marketLeaders.mostVolatile")}
        entry={mostVolatile}
        value={(e) => formatSignedPercent(e.volatility_percent)}
        subtitle={() => t("marketLeaders.volatilitySubtitle", { period: periodLabel })}
      />
    </div>
  );
}
