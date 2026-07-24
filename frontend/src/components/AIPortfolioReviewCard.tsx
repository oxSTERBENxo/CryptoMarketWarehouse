import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { postPortfolioReview } from "../api/ai";
import { ApiError } from "../api/client";
import type { PortfolioReviewResponse } from "../api/types";
import { AIPortfolioReviewSkeleton } from "./AIPortfolioReviewSkeleton";
import { PortfolioAIInsightsPanel } from "./PortfolioAIInsightsPanel";
import { PortfolioHealthCards } from "./PortfolioHealthCards";
import { PortfolioTopHoldingsCards } from "./PortfolioTopHoldingsCards";
import { formatDateTime } from "../utils/format";
import "./AIMarketSummaryCard.css";
import "./AICoinAnalysisCard.css";
import "./AIPortfolioReviewCard.css";

/** The Portfolio page's "AI Portfolio Review" tab (POST /ai/portfolio-review): an educational
 * review of the user's simulated paper-trading portfolio, built from the same request/response
 * pattern as AIMarketSummaryCard/AICoinAnalysisCard. Every number, score, and classification shown
 * in PortfolioHealthCards/PortfolioTopHoldingsCards is computed deterministically in the backend
 * (ai_portfolio_review_service.py); the AI only writes the five short "AI Review" bullet sections,
 * and it never recommends buying, selling, or holding anything. Nothing is generated
 * automatically -- the user must click Generate/Refresh. The last successful review stays on
 * screen through a Refresh's loading/error states, so a failed regeneration never blanks out a
 * review the user was already reading. */
export function AIPortfolioReviewCard() {
  const { t } = useTranslation();
  const [review, setReview] = useState<PortfolioReviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlightRef = useRef(false);

  async function handleGenerate() {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setLoading(true);
    setError(null);

    try {
      const data = await postPortfolioReview();
      setReview(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("common.somethingWentWrong"));
    } finally {
      inFlightRef.current = false;
      setLoading(false);
    }
  }

  return (
    <section aria-labelledby="ai-portfolio-review-heading" className="ai-market-summary-section">
      <div className="ai-market-summary-header">
        <h2 id="ai-portfolio-review-heading">{t("ai.portfolioReview.title")}</h2>
        {review && (
          <button
            type="button"
            className="ai-market-summary__refresh"
            onClick={handleGenerate}
            disabled={loading}
            aria-busy={loading}
          >
            {loading && <span className="status-spinner" aria-hidden="true" />}
            {t("ai.common.refresh")}
          </button>
        )}
      </div>

      <p className="ai-portfolio-review__disclaimer">{t("ai.portfolioReview.disclaimer")}</p>

      <div className="ai-market-summary-card">
        {!review && (
          <div className="ai-market-summary__intro">
            {!loading && !error && <p>{t("ai.portfolioReview.noReview")}</p>}
            {!loading && error && (
              <p className="ai-market-summary__error" role="alert">
                {t("ai.portfolioReview.generateError", { error })}
              </p>
            )}
            <button
              type="button"
              className="ai-market-summary__generate"
              onClick={handleGenerate}
              disabled={loading}
              aria-busy={loading}
            >
              {loading && <span className="status-spinner" aria-hidden="true" />}
              {loading ? t("ai.portfolioReview.generating") : error ? t("ai.common.tryAgain") : t("ai.portfolioReview.generate")}
            </button>
          </div>
        )}

        {!review && loading && <AIPortfolioReviewSkeleton />}

        {review && error && (
          <p className="ai-market-summary__error ai-market-summary__error--inline" role="alert">
            {t("ai.portfolioReview.refreshError", { error })}
          </p>
        )}

        {review && (
          <div className="ai-market-summary__body">
            <h3 className="ai-coin-analysis__subheading">{t("ai.portfolioReview.portfolioHealth")}</h3>
            <PortfolioHealthCards health={review.portfolio_health} numberOfPositions={review.portfolio_summary.number_of_positions} />

            <h3 className="ai-coin-analysis__subheading">{t("ai.portfolioReview.topHoldings")}</h3>
            <PortfolioTopHoldingsCards positions={review.top_positions} />

            <h3 className="ai-coin-analysis__subheading">{t("ai.portfolioReview.aiReview")}</h3>
            <PortfolioAIInsightsPanel insights={review.ai_insights} />

            <div className="ai-market-summary__meta">
              <span>{t("ai.common.provider", { provider: review.provider })}</span>
              <span>{t("ai.common.model", { model: review.model })}</span>
              <span>{t("ai.common.generatedAt", { time: formatDateTime(review.generated_at) })}</span>
              <span>{t("ai.common.generationTime", { seconds: (review.response_time_ms / 1000).toFixed(1) })}</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
