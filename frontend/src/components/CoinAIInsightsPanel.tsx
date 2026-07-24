import { useTranslation } from "react-i18next";
import type { CoinAIInsights } from "../api/types";
import { InsightList } from "./AIInsightsPanel";
import "./AIInsightsPanel.css";
import "./CoinAIInsightsPanel.css";

interface CoinAIInsightsPanelProps {
  insights: CoinAIInsights;
}

/** The AI Coin Analysis card's five short bullet sections -- the only AI-authored part of the
 * response, interpreting the deterministic CoinHealthCards/CoinInformation shown elsewhere rather
 * than a source of any figure itself (see ai_coin_analysis_service.py /
 * ai_prompt_builder.build_coin_analysis). Reuses AIInsightsPanel's InsightList so both AI
 * features' bullet sections render identically. */
export function CoinAIInsightsPanel({ insights }: CoinAIInsightsPanelProps) {
  const { t } = useTranslation();
  return (
    <div className="ai-insights coin-ai-insights">
      <div className="ai-insights__section">
        <h4>{t("ai.coinAnalysis.sections.interpretation")}</h4>
        <InsightList items={insights.overview} />
      </div>
      <div className="ai-insights__section">
        <h4>{t("ai.coinAnalysis.sections.performance")}</h4>
        <InsightList items={insights.performance} />
      </div>
      <div className="ai-insights__section">
        <h4>{t("ai.coinAnalysis.sections.marketPosition")}</h4>
        <InsightList items={insights.market_position} />
      </div>
      <div className="ai-insights__section">
        <h4>{t("ai.coinAnalysis.sections.thingsToWatch")}</h4>
        <InsightList items={insights.things_to_watch} />
      </div>
      <div className="ai-insights__section">
        <h4>{t("ai.coinAnalysis.sections.risk")}</h4>
        <InsightList items={insights.risk} />
      </div>
    </div>
  );
}
