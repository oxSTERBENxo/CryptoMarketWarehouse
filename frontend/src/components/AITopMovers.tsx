import { useTranslation } from "react-i18next";
import type { MarketCoinEntry } from "../api/types";
import { MarketCoinRow } from "./MarketCoinRow";
import "./MarketCoinRow.css";
import "./AITopMovers.css";

interface AITopMoversProps {
  gainers: MarketCoinEntry[];
  losers: MarketCoinEntry[];
}

/** Section 4 (Top Movers): gainers and losers side by side, each row showing logo, price, 24h
 * change, and volume -- never a plain numbered Markdown list. */
export function AITopMovers({ gainers, losers }: AITopMoversProps) {
  const { t } = useTranslation();
  return (
    <div className="ai-top-movers">
      <div className="ai-top-movers__column">
        <h4 className="ai-top-movers__heading ai-top-movers__heading--gain">{t("ai.topMovers.gainers")}</h4>
        {gainers.length === 0 ? (
          <p className="market-coin-list__empty">{t("ai.topMovers.noGainers")}</p>
        ) : (
          <ul className="market-coin-list">
            {gainers.map((coin, index) => (
              <MarketCoinRow key={coin.coin_id} coin={coin} rank={index + 1} />
            ))}
          </ul>
        )}
      </div>
      <div className="ai-top-movers__column">
        <h4 className="ai-top-movers__heading ai-top-movers__heading--loss">{t("ai.topMovers.losers")}</h4>
        {losers.length === 0 ? (
          <p className="market-coin-list__empty">{t("ai.topMovers.noLosers")}</p>
        ) : (
          <ul className="market-coin-list">
            {losers.map((coin, index) => (
              <MarketCoinRow key={coin.coin_id} coin={coin} rank={index + 1} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
