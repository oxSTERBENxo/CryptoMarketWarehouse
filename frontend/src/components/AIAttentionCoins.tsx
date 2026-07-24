import { useTranslation } from "react-i18next";
import type { AttentionCategory, AttentionCoin } from "../api/types";
import { MarketCoinRow } from "./MarketCoinRow";
import "./MarketCoinRow.css";
import "./AIAttentionCoins.css";

interface AIAttentionCoinsProps {
  coins: AttentionCoin[];
}

const CATEGORY_ORDER: AttentionCategory[] = ["positive_momentum", "most_active", "unusual_activity"];

/** Section 3 (Coins Attracting Attention): attention_coins grouped by its deterministic category
 * (see ai_market_summary_service.py -- the AI never chooses these, only application code does).
 * Always visible, never collapsible, per the "understand it in a few seconds" requirement. */
export function AIAttentionCoins({ coins }: AIAttentionCoinsProps) {
  const { t } = useTranslation();
  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    entries: coins.filter((c) => c.category === category),
  })).filter((group) => group.entries.length > 0);

  return (
    <section aria-labelledby="ai-attention-heading" className="ai-attention">
      <h3 id="ai-attention-heading">{t("ai.attention.title")}</h3>
      {groups.length === 0 ? (
        <p className="ai-attention__empty">{t("ai.attention.empty")}</p>
      ) : (
        <div className="ai-attention__groups">
          {groups.map((group) => (
            <div key={group.category} className="ai-attention__group">
              <h4>{t(`ai.attention.categories.${group.category}`)}</h4>
              <ul className="market-coin-list">
                {group.entries.map((coin) => (
                  <MarketCoinRow key={`${group.category}-${coin.coin_id}`} coin={coin} note={coin.reason} />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
      <p className="ai-attention__disclaimer">{t("ai.attention.disclaimer")}</p>
    </section>
  );
}
