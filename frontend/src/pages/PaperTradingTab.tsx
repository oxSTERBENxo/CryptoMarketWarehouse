import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { buyPaperTrade, getPaperPortfolio, getPaperTrades, resetPaperAccount, sellPaperTrade } from "../api/paperTrading";
import { useApiData } from "../hooks/useApiData";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { TradeModal } from "../components/TradeModal";
import type { TradeFormValues } from "../components/TradeModal";
import { PaperHoldingsTable } from "../components/PaperHoldingsTable";
import { PaperTransactionsTable } from "../components/PaperTransactionsTable";
import { AllocationBars } from "../components/AllocationBars";
import { AchievementBadges } from "../components/AchievementBadges";
import { HealthScoreCard } from "../components/HealthScoreCard";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { computeAchievements } from "../utils/achievements";
import { computeHealthScore } from "../utils/healthScore";
import { formatSignedPercent, formatSignedUsd, formatUsd } from "../utils/format";
import type { PaperHolding } from "../api/types";
import "../components/OverviewCards.css";
import "./PaperTradingTab.css";

const TRADE_HISTORY_LIMIT = 50;

type ModalState =
  | { kind: "none" }
  | { kind: "buy" }
  | { kind: "sell" }
  | { kind: "buy-more"; holding: PaperHolding }
  | { kind: "sell-holding"; holding: PaperHolding }
  | { kind: "reset" };

function profitClass(value: number | null): string {
  if (value === null || value === 0) return "profit-neutral";
  return value > 0 ? "profit-positive" : "profit-negative";
}

export function PaperTradingTab() {
  const { t } = useTranslation();
  const portfolio = useApiData(getPaperPortfolio);
  const trades = useApiData(() => getPaperTrades(TRADE_HISTORY_LIMIT));
  const [modal, setModal] = useState<ModalState>({ kind: "none" });
  const closeModal = () => setModal({ kind: "none" });

  const refresh = () => {
    portfolio.retry();
    trades.retry();
  };

  const achievements = useMemo(
    () => (portfolio.data ? computeAchievements(portfolio.data, trades.data ?? [], t) : []),
    [portfolio.data, trades.data, t]
  );
  const healthScore = useMemo(
    () => (portfolio.data ? computeHealthScore(portfolio.data, t) : null),
    [portfolio.data, t]
  );

  const loading = portfolio.loading || trades.loading;
  const error = portfolio.error ?? trades.error;

  return (
    <div className="paper-trading-tab">
      <p className="paper-trading-tab__disclaimer">{t("portfolio.paper.disclaimer")}</p>

      {loading && <LoadingState label={t("portfolio.paper.loadingAccount")} />}
      {!loading && error && <ErrorState message={error} onRetry={refresh} />}

      {!loading && !error && portfolio.data && healthScore && (
        <>
          <section className="paper-trading-tab__header">
            <div>
              <h2>{portfolio.data.account.name}</h2>
              <p className="paper-trading-tab__return">
                {t("portfolio.paper.totalReturn")}:{" "}
                <span className={profitClass(portfolio.data.total_return_percent)}>
                  {formatSignedPercent(portfolio.data.total_return_percent)}
                </span>
              </p>
            </div>
            <div className="paper-trading-tab__actions">
              <button type="button" className="modal-button modal-button--primary" onClick={() => setModal({ kind: "buy" })}>
                {t("portfolio.paper.buy")}
              </button>
              <button
                type="button"
                className="modal-button"
                onClick={() => setModal({ kind: "sell" })}
                disabled={portfolio.data.holdings.length === 0}
              >
                {t("portfolio.paper.sell")}
              </button>
              <button type="button" className="modal-button" onClick={() => setModal({ kind: "reset" })}>
                {t("portfolio.paper.resetAccount")}
              </button>
            </div>
          </section>

          <dl className="overview-grid">
            <div className="overview-card">
              <dt>{t("portfolio.paper.totalEquity")}</dt>
              <dd>{formatUsd(portfolio.data.total_equity)}</dd>
            </div>
            <div className="overview-card">
              <dt>{t("portfolio.paper.availableCash")}</dt>
              <dd>{formatUsd(portfolio.data.cash_balance)}</dd>
            </div>
            <div className="overview-card">
              <dt>{t("portfolio.paper.investedAmount")}</dt>
              <dd>{formatUsd(portfolio.data.invested_value)}</dd>
            </div>
            <div className="overview-card">
              <dt>{t("portfolio.paper.realizedPl")}</dt>
              <dd className={profitClass(portfolio.data.realized_profit)}>{formatSignedUsd(portfolio.data.realized_profit)}</dd>
            </div>
            <div className="overview-card">
              <dt>{t("portfolio.paper.unrealizedPl")}</dt>
              <dd className={profitClass(portfolio.data.unrealized_profit)}>
                {formatSignedUsd(portfolio.data.unrealized_profit)}
              </dd>
            </div>
            <div className="overview-card">
              <dt>{t("portfolio.paper.bestWorstPerformer")}</dt>
              <dd className="paper-trading-tab__performers">
                <span className="profit-positive">{portfolio.data.best_performer ?? "—"}</span>
                {" / "}
                <span className="profit-negative">{portfolio.data.worst_performer ?? "—"}</span>
              </dd>
            </div>
          </dl>

          <div className="paper-trading-tab__grid">
            <HealthScoreCard healthScore={healthScore} />
            <div className="paper-trading-tab__side-card">
              <h3>{t("portfolio.paper.allocation")}</h3>
              <AllocationBars
                holdings={portfolio.data.holdings}
                cashBalance={portfolio.data.cash_balance}
                totalEquity={portfolio.data.total_equity}
              />
            </div>
          </div>

          <section aria-labelledby="achievements-heading" className="table-section">
            <h2 id="achievements-heading">{t("portfolio.paper.achievements")}</h2>
            <AchievementBadges achievements={achievements} />
          </section>

          <section aria-labelledby="paper-holdings-heading" className="table-section">
            <h2 id="paper-holdings-heading">{t("portfolio.manual.holdings")}</h2>
            {portfolio.data.holdings.length === 0 ? (
              <EmptyState message={t("portfolio.paper.noHoldingsYet")} />
            ) : (
              <PaperHoldingsTable
                holdings={portfolio.data.holdings}
                onBuyMore={(holding) => setModal({ kind: "buy-more", holding })}
                onSell={(holding) => setModal({ kind: "sell-holding", holding })}
              />
            )}
          </section>

          <section aria-labelledby="paper-history-heading" className="table-section">
            <h2 id="paper-history-heading">{t("portfolio.paper.transactionHistory")}</h2>
            {(trades.data ?? []).length === 0 ? (
              <EmptyState message={t("portfolio.paper.noTradesYet")} />
            ) : (
              <PaperTransactionsTable transactions={trades.data ?? []} />
            )}
          </section>
        </>
      )}

      {(modal.kind === "buy" || modal.kind === "buy-more") && portfolio.data && (
        <TradeModal
          mode="buy"
          fixedSymbol={modal.kind === "buy-more" ? modal.holding.coin_symbol : undefined}
          fixedCoinName={modal.kind === "buy-more" ? modal.holding.coin_name : undefined}
          cashBalance={portfolio.data.cash_balance}
          onSubmit={async (values: TradeFormValues) => {
            await buyPaperTrade(values);
            refresh();
          }}
          onClose={closeModal}
        />
      )}

      {(modal.kind === "sell" || modal.kind === "sell-holding") && portfolio.data && (
        <TradeModal
          mode="sell"
          fixedSymbol={modal.kind === "sell-holding" ? modal.holding.coin_symbol : undefined}
          fixedCoinName={modal.kind === "sell-holding" ? modal.holding.coin_name : undefined}
          sellableHoldings={portfolio.data.holdings}
          cashBalance={portfolio.data.cash_balance}
          onSubmit={async (values: TradeFormValues) => {
            await sellPaperTrade(values);
            refresh();
          }}
          onClose={closeModal}
        />
      )}

      {modal.kind === "reset" && (
        <ConfirmDialog
          title={t("portfolio.paper.resetAccount")}
          message={t("portfolio.paper.resetConfirm")}
          confirmLabel={t("portfolio.paper.resetAccount")}
          onConfirm={async () => {
            await resetPaperAccount();
            refresh();
          }}
          onClose={closeModal}
        />
      )}
    </div>
  );
}
