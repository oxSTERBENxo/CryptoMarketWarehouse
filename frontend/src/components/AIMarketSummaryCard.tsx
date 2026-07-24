import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { postMarketSummary } from "../api/ai";
import { ApiError } from "../api/client";
import type { MarketSummaryResponse } from "../api/types";
import { AIAttentionCoins } from "./AIAttentionCoins";
import { AIInsightsPanel } from "./AIInsightsPanel";
import { AIMarketOverviewSection } from "./AIMarketOverviewSection";
import { AIMarketSummarySkeleton } from "./AIMarketSummarySkeleton";
import { AITopMovers } from "./AITopMovers";
import { AITradingActivity } from "./AITradingActivity";
import { formatDateTime } from "../utils/format";
import "./AIMarketSummaryCard.css";

/** Dashboard card for the AI Market Summary feature (POST /ai/market-summary): a structured
 * market-intelligence view built from dedicated React components, not a Markdown blob. Every
 * number, ranking, and category is computed deterministically in the backend
 * (ai_market_summary_service.py) -- the AI only writes the three short "AI Insights" bullet
 * sections, which interpret the data shown elsewhere rather than restate it.
 *
 * Nothing is generated automatically; each press is a real AI call, so the user must click
 * Generate/Refresh. The last successful summary stays on screen through a Refresh's
 * loading/error states, so a failed regeneration never blanks out a report the user was already
 * reading. */
export function AIMarketSummaryCard() {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<MarketSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlightRef = useRef(false);

  async function handleGenerate() {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setLoading(true);
    setError(null);

    try {
      const data = await postMarketSummary();
      setSummary(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("common.somethingWentWrong"));
    } finally {
      inFlightRef.current = false;
      setLoading(false);
    }
  }

  return (
    <section aria-labelledby="ai-market-summary-heading" className="ai-market-summary-section">
      <div className="ai-market-summary-header">
        <h2 id="ai-market-summary-heading">{t("ai.marketSummary.title")}</h2>
        {summary && (
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

      <div className="ai-market-summary-card">
        {!summary && (
          <div className="ai-market-summary__intro">
            {!loading && !error && <p>{t("ai.marketSummary.noSummary")}</p>}
            {!loading && error && (
              <p className="ai-market-summary__error" role="alert">
                {t("ai.marketSummary.generateError", { error })}
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
              {loading ? t("ai.marketSummary.generating") : error ? t("ai.common.tryAgain") : t("ai.marketSummary.generate")}
            </button>
          </div>
        )}

        {!summary && loading && <AIMarketSummarySkeleton />}

        {summary && error && (
          <p className="ai-market-summary__error ai-market-summary__error--inline" role="alert">
            {t("ai.marketSummary.refreshError", { error })}
          </p>
        )}

        {summary && (
          <div className="ai-market-summary__body">
            <AIMarketOverviewSection status={summary.market_status} metrics={summary.metrics} />

            <AIAttentionCoins coins={summary.attention_coins} />

            <details className="ai-market-summary__collapsible" open>
              <summary>{t("ai.marketSummary.topMovers")}</summary>
              <AITopMovers gainers={summary.top_gainers} losers={summary.top_losers} />
            </details>

            <details className="ai-market-summary__collapsible" open>
              <summary>{t("ai.marketSummary.tradingActivity")}</summary>
              <AITradingActivity coins={summary.most_active} />
            </details>

            <details className="ai-market-summary__collapsible" open>
              <summary>{t("ai.marketSummary.aiInsights")}</summary>
              <AIInsightsPanel insights={summary.ai_insights} />
            </details>

            <div className="ai-market-summary__meta">
              <span>{t("ai.common.provider", { provider: summary.provider })}</span>
              <span>{t("ai.common.model", { model: summary.model })}</span>
              <span>{t("ai.common.generatedAt", { time: formatDateTime(summary.generated_at) })}</span>
              <span>{t("ai.common.generationTime", { seconds: (summary.response_time_ms / 1000).toFixed(1) })}</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
