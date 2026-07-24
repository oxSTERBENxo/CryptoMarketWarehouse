import { useTranslation } from "react-i18next";
import type { PortfolioAIInsights } from "../api/types";
import { InsightList } from "./AIInsightsPanel";
import "./AIInsightsPanel.css";

interface PortfolioAIInsightsPanelProps {
  insights: PortfolioAIInsights;
}

/** The AI Portfolio Review card's five short bullet sections -- the only AI-authored part of the
 * response, interpreting the deterministic PortfolioHealthCards/PortfolioTopHoldingsCards shown
 * elsewhere rather than a source of any figure itself (see ai_portfolio_review_service.py /
 * ai_prompt_builder.build_portfolio_analysis). Reuses AIInsightsPanel's InsightList so every AI
 * feature's bullet sections render identically. Never a buy/sell recommendation. */
export function PortfolioAIInsightsPanel({ insights }: PortfolioAIInsightsPanelProps) {
  const { t } = useTranslation();
  return (
    <div className="ai-insights">
      <div className="ai-insights__section">
        <h4>{t("ai.portfolioReview.sections.strengths")}</h4>
        <InsightList items={insights.strengths} />
      </div>
      <div className="ai-insights__section">
        <h4>{t("ai.portfolioReview.sections.weaknesses")}</h4>
        <InsightList items={insights.weaknesses} />
      </div>
      <div className="ai-insights__section">
        <h4>{t("ai.portfolioReview.sections.interestingObservations")}</h4>
        <InsightList items={insights.interesting_observations} />
      </div>
      <div className="ai-insights__section">
        <h4>{t("ai.portfolioReview.sections.riskFactors")}</h4>
        <InsightList items={insights.risk_factors} />
      </div>
      <div className="ai-insights__section">
        <h4>{t("ai.portfolioReview.sections.educationalNotes")}</h4>
        <InsightList items={insights.educational_notes} />
      </div>
    </div>
  );
}
