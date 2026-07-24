import { useTranslation } from "react-i18next";
import type { MarketCoinEntry } from "../api/types";
import { CoinLogo } from "./CoinLogo";
import { PercentChangeBadge } from "./PercentChangeBadge";
import { useRowNavigate } from "../hooks/useRowNavigate";
import { formatCompactUsd, formatCryptoPrice } from "../utils/format";
import "./MarketCoinRow.css";

interface MarketCoinRowProps {
  coin: MarketCoinEntry;
  /** Optional leading rank number (1-based). */
  rank?: number;
  /** Optional trailing note under the name -- an attention reason, a volume-share figure, etc.
   * Never a buy/sell recommendation. */
  note?: string;
}

/** One clickable coin row (logo, name/symbol, price, 24h change, 24h volume), shared by the
 * Attention Coins, Top Movers, and Trading Activity sections of the AI Market Summary card. The
 * whole row navigates to Coin Details, same convention as MarketMoverList's rows elsewhere in the
 * dashboard. Must be rendered inside a <ul>/<ol>. */
export function MarketCoinRow({ coin, rank, note }: MarketCoinRowProps) {
  const { t } = useTranslation();
  const rowProps = useRowNavigate(coin.symbol, t("common.openDetails", { name: coin.name }));

  return (
    <li className="market-coin-row" {...rowProps}>
      {/* Always rendered (even blank) so the grid's column count stays fixed regardless of
       * whether this list uses ranks -- omitting the element entirely shifts every following
       * cell one column left instead of leaving the rank slot empty. */}
      <span className="market-coin-row__rank">{rank ?? ""}</span>
      <CoinLogo src={coin.image_url} name={coin.name} size={28} />
      <span className="market-coin-row__identity">
        <span className="market-coin-row__name">
          {coin.name} <span className="market-coin-row__symbol">{coin.symbol.toUpperCase()}</span>
        </span>
        {note && <span className="market-coin-row__note">{note}</span>}
      </span>
      <span className="market-coin-row__price">{formatCryptoPrice(coin.price)}</span>
      <PercentChangeBadge value={coin.change_24h} />
      <span className="market-coin-row__volume">{formatCompactUsd(coin.volume_24h)}</span>
    </li>
  );
}
