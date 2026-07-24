import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { postCoinAnalysis } from "../api/ai";
import { ApiError } from "../api/client";
import type { CoinAnalysisResponse } from "../api/types";
import { AICoinAnalysisSkeleton } from "./AICoinAnalysisSkeleton";
import { CoinAIInsightsPanel } from "./CoinAIInsightsPanel";
import { CoinHealthCards } from "./CoinHealthCards";
import { formatDateTime } from "../utils/format";
import "./AIMarketSummaryCard.css";
import "./AICoinAnalysisCard.css";

interface AICoinAnalysisCardProps {
  /** The coin symbol from the Coin Details route (e.g. "btc"), passed straight to
   * POST /ai/coin-analysis/{coinSymbol}. */
  symbol: string;
}

/** Coin Details' "AI Coin Analysis" section (POST /ai/coin-analysis/{coin_symbol}): the flagship
 * AI feature, built from the same request/response pattern as AIMarketSummaryCard -- nothing is
 * generated automatically, every number/trend/level shown in CoinHealthCards is computed
 * deterministically in the backend (ai_coin_analysis_service.py), and the AI only writes the five
 * short "AI Interpretation" bullet sections. The last successful analysis stays on screen through
 * a Refresh's loading/error states, so a failed regeneration never blanks out an analysis the user
 * was already reading. */
export function AICoinAnalysisCard({ symbol }: AICoinAnalysisCardProps) {
  const { t } = useTranslation();
  const [analysis, setAnalysis] = useState<CoinAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlightRef = useRef(false);

  // Switching coins must never keep showing a previous coin's analysis or in-flight state.
  useEffect(() => {
    setAnalysis(null);
    setLoading(false);
    setError(null);
    inFlightRef.current = false;
  }, [symbol]);

  async function handleGenerate() {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setLoading(true);
    setError(null);

    try {
      const data = await postCoinAnalysis(symbol);
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("common.somethingWentWrong"));
    } finally {
      inFlightRef.current = false;
      setLoading(false);
    }
  }

  return (
    <section aria-labelledby="ai-coin-analysis-heading" className="ai-market-summary-section">
      <div className="ai-market-summary-header">
        <h2 id="ai-coin-analysis-heading">{t("ai.coinAnalysis.title")}</h2>
        {analysis && (
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
        {!analysis && (
          <div className="ai-market-summary__intro">
            {!loading && !error && <p>{t("ai.coinAnalysis.noAnalysis")}</p>}
            {!loading && error && (
              <p className="ai-market-summary__error" role="alert">
                {t("ai.coinAnalysis.generateError", { error })}
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
              {loading ? t("ai.coinAnalysis.generating") : error ? t("ai.common.tryAgain") : t("ai.coinAnalysis.generate")}
            </button>
          </div>
        )}

        {!analysis && loading && <AICoinAnalysisSkeleton />}

        {analysis && error && (
          <p className="ai-market-summary__error ai-market-summary__error--inline" role="alert">
            {t("ai.coinAnalysis.refreshError", { error })}
          </p>
        )}

        {analysis && (
          <div className="ai-market-summary__body">
            <h3 className="ai-coin-analysis__subheading">{t("ai.coinAnalysis.coinHealth")}</h3>
            <CoinHealthCards metrics={analysis.deterministic_metrics} />

            <CoinAIInsightsPanel insights={analysis.ai_insights} />

            <div className="ai-market-summary__meta">
              <span>{t("ai.common.provider", { provider: analysis.provider })}</span>
              <span>{t("ai.common.model", { model: analysis.model })}</span>
              <span>{t("ai.common.generatedAt", { time: formatDateTime(analysis.generated_at) })}</span>
              <span>{t("ai.common.generationTime", { seconds: (analysis.response_time_ms / 1000).toFixed(1) })}</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
