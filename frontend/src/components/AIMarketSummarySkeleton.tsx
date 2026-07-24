import { useTranslation } from "react-i18next";
import "./AIMarketSummarySkeleton.css";

/** Loading skeleton shown only for the first generation (before any summary exists) -- a rough
 * preview of the eventual layout (status badge + headline, 4 metric cards, a short list) instead
 * of a bare spinner, so the shape of the incoming content is already legible while waiting. */
export function AIMarketSummarySkeleton() {
  const { t } = useTranslation();
  return (
    <div className="ai-skeleton" role="status" aria-label={t("ai.marketSummary.skeletonLabel")}>
      <div className="ai-skeleton__row">
        <span className="ai-skeleton__badge" />
        <span className="ai-skeleton__line ai-skeleton__line--wide" />
      </div>
      <div className="ai-skeleton__cards">
        <span className="ai-skeleton__card" />
        <span className="ai-skeleton__card" />
        <span className="ai-skeleton__card" />
        <span className="ai-skeleton__card" />
      </div>
      <div className="ai-skeleton__list">
        <span className="ai-skeleton__line" />
        <span className="ai-skeleton__line" />
        <span className="ai-skeleton__line" />
      </div>
    </div>
  );
}
