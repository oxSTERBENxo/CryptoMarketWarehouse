import { useTranslation } from "react-i18next";
import type { AIInsights } from "../api/types";
import "./AIInsightsPanel.css";

interface AIInsightsPanelProps {
  insights: AIInsights;
}

/** Shared bullet-list-or-empty-state rendering for any AI-authored insight section -- reused by
 * CoinAIInsightsPanel so the two AI features' interpretive sections render identically. */
export function InsightList({ items }: { items: string[] }) {
  const { t } = useTranslation();
  if (items.length === 0) {
    return <p className="ai-insights__empty">{t("ai.insights.empty")}</p>;
  }
  return (
    <ul>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

/** Section 6 (AI Insights): the only AI-authored part of the card, limited to three short bullet
 * sections that interpret the deterministic data shown elsewhere -- never a source of numbers or
 * rankings itself (see ai_market_summary_service.py / build_market_summary). */
export function AIInsightsPanel({ insights }: AIInsightsPanelProps) {
  const { t } = useTranslation();
  return (
    <div className="ai-insights">
      <div className="ai-insights__section">
        <h4>{t("ai.insights.marketOverview")}</h4>
        <InsightList items={insights.market_overview} />
      </div>
      <div className="ai-insights__section">
        <h4>{t("ai.insights.whatStandsOut")}</h4>
        <InsightList items={insights.what_stands_out} />
      </div>
      <div className="ai-insights__section">
        <h4>{t("ai.insights.riskAndCaution")}</h4>
        <InsightList items={insights.risk_and_caution} />
      </div>
    </div>
  );
}
