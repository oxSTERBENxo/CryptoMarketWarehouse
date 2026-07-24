import { useTranslation } from "react-i18next";
import type { PortfolioPosition } from "../api/types";
import { CoinLink } from "./CoinLink";
import { CoinLogo } from "./CoinLogo";
import { PercentChangeBadge } from "./PercentChangeBadge";
import { formatUsd } from "../utils/format";
import "./PortfolioTopHoldingsCards.css";

interface PortfolioTopHoldingsCardsProps {
  positions: PortfolioPosition[];
}

/** "Top Holdings" cards for the AI Portfolio Review tab -- allocation-ranked (server-side, capped
 * at ai_portfolio_review_service.TOP_POSITIONS_LIMIT), each showing the coin's logo, symbol,
 * allocation share, current value, and 24h change. Purely presentational: every figure comes
 * straight from the deterministic PortfolioPosition the backend already computed. */
export function PortfolioTopHoldingsCards({ positions }: PortfolioTopHoldingsCardsProps) {
  const { t } = useTranslation();
  if (positions.length === 0) {
    return <p className="portfolio-top-holdings__empty">{t("ai.portfolioReview.noHoldings")}</p>;
  }

  return (
    <div className="portfolio-top-holdings">
      {positions.map((position) => (
        <article key={position.coin_symbol} className="portfolio-top-holding-card">
          <CoinLink symbol={position.coin_symbol}>
            <span className="portfolio-top-holding-card__coin">
              <CoinLogo src={position.image_url} name={position.coin_name ?? position.coin_symbol} size={26} />
              <span>
                <span className="portfolio-top-holding-card__symbol">{position.coin_symbol}</span>
                {position.coin_name && <span className="portfolio-top-holding-card__name"> {position.coin_name}</span>}
              </span>
            </span>
          </CoinLink>

          <div className="portfolio-top-holding-card__allocation">
            {position.allocation_percent !== null ? `${position.allocation_percent.toFixed(1)}%` : "—"}
            <span className="portfolio-top-holding-card__allocation-label">{t("ai.portfolioReview.ofPortfolio")}</span>
          </div>

          <dl className="portfolio-top-holding-card__stats">
            <div>
              <dt>{t("ai.portfolioReview.value")}</dt>
              <dd>{formatUsd(position.current_value)}</dd>
            </div>
            <div>
              <dt>24h</dt>
              <dd>
                <PercentChangeBadge value={position.price_change_percentage_24h} />
              </dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  );
}
