import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PaperTradingTab } from "./PaperTradingTab";
import { ManualHoldingsTab } from "./ManualHoldingsTab";
import { AIPortfolioReviewCard } from "../components/AIPortfolioReviewCard";
import "./Portfolio.css";

type TabKey = "paper-trading" | "manual-holdings" | "ai-portfolio-review";

const TAB_KEYS: { key: TabKey; labelKey: string }[] = [
  { key: "paper-trading", labelKey: "portfolio.tabs.paperTrading" },
  { key: "manual-holdings", labelKey: "portfolio.tabs.manualHoldings" },
  { key: "ai-portfolio-review", labelKey: "portfolio.tabs.aiPortfolioReview" },
];

export function Portfolio() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabKey>("paper-trading");

  return (
    <main className="portfolio-page">
      <h1 className="portfolio-page__title">{t("nav.portfolio")}</h1>

      <div className="portfolio-page__tabs" role="tablist" aria-label={t("portfolio.tabsLabel")}>
        {TAB_KEYS.map((tabOption) => (
          <button
            key={tabOption.key}
            type="button"
            role="tab"
            aria-selected={tab === tabOption.key}
            className={`portfolio-page__tab ${tab === tabOption.key ? "portfolio-page__tab--active" : ""}`}
            onClick={() => setTab(tabOption.key)}
          >
            {t(tabOption.labelKey)}
          </button>
        ))}
      </div>

      {tab === "paper-trading" && <PaperTradingTab />}
      {tab === "manual-holdings" && <ManualHoldingsTab />}
      {tab === "ai-portfolio-review" && <AIPortfolioReviewCard />}
    </main>
  );
}
