import { useTranslation } from "react-i18next";
import type { MarketCoinEntry } from "../api/types";
import { MarketCoinRow } from "./MarketCoinRow";
import "./MarketCoinRow.css";

interface AITradingActivityProps {
  coins: MarketCoinEntry[];
}

/** Section 5 (Trading Activity): the five highest-volume coins, each row's note showing its share
 * of the total tracked 24h volume (ai_market_summary_service._to_entry's volume_share_percent)
 * when it can be calculated. */
export function AITradingActivity({ coins }: AITradingActivityProps) {
  const { t } = useTranslation();

  function shareNote(coin: MarketCoinEntry): string | undefined {
    if (coin.volume_share_percent === null || coin.volume_share_percent === undefined) return undefined;
    return t("ai.tradingActivity.volumeShare", { percent: coin.volume_share_percent.toFixed(1) });
  }

  if (coins.length === 0) {
    return <p className="market-coin-list__empty">{t("ai.tradingActivity.empty")}</p>;
  }

  return (
    <ul className="market-coin-list">
      {coins.map((coin, index) => (
        <MarketCoinRow key={coin.coin_id} coin={coin} rank={index + 1} note={shareNote(coin)} />
      ))}
    </ul>
  );
}
