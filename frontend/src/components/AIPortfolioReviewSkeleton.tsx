import { useTranslation } from "react-i18next";
import "./AIMarketSummarySkeleton.css";

/** Loading skeleton shown only for the first generation (before any review exists) -- reuses
 * AIMarketSummarySkeleton's shimmer building blocks (status cards + list lines) rather than
 * inventing a new loading treatment. */
export function AIPortfolioReviewSkeleton() {
  const { t } = useTranslation();
  return (
    <div className="ai-skeleton" role="status" aria-label={t("ai.portfolioReview.skeletonLabel")}>
      <div className="ai-skeleton__cards">
        <span className="ai-skeleton__card" />
        <span className="ai-skeleton__card" />
        <span className="ai-skeleton__card" />
        <span className="ai-skeleton__card" />
        <span className="ai-skeleton__card" />
        <span className="ai-skeleton__card" />
      </div>
      <div className="ai-skeleton__list">
        <span className="ai-skeleton__line" />
        <span className="ai-skeleton__line" />
        <span className="ai-skeleton__line" />
        <span className="ai-skeleton__line" />
      </div>
    </div>
  );
}
