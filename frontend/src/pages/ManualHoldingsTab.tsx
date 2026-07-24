import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  addHolding,
  createPortfolio,
  deleteHolding,
  deletePortfolio,
  getPortfolios,
  updateHolding,
  updatePortfolio,
} from "../api/portfolio";
import { useApiData } from "../hooks/useApiData";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { PortfolioSummaryCards } from "../components/PortfolioSummaryCards";
import { HoldingsTable } from "../components/HoldingsTable";
import { PortfolioFormModal } from "../components/PortfolioFormModal";
import { HoldingFormModal } from "../components/HoldingFormModal";
import { ConfirmDialog } from "../components/ConfirmDialog";
import type { Holding } from "../api/types";
import "./Portfolio.css";

type ModalState =
  | { kind: "none" }
  | { kind: "create-portfolio" }
  | { kind: "rename-portfolio" }
  | { kind: "delete-portfolio" }
  | { kind: "add-holding" }
  | { kind: "edit-holding"; holding: Holding }
  | { kind: "delete-holding"; holding: Holding };

/** The original static holdings CRUD ledger (manually entered quantity + average buy price,
 * valued from the warehouse). Unchanged behavior — kept as a secondary tab alongside the newer
 * Paper Trading simulator so nothing existing is removed. */
export function ManualHoldingsTab() {
  const { t } = useTranslation();
  const portfolios = useApiData(getPortfolios);
  const [modal, setModal] = useState<ModalState>({ kind: "none" });
  const closeModal = () => setModal({ kind: "none" });

  // Single-portfolio focus: manage the first portfolio the account has. The REST API supports
  // many, but the UI intentionally keeps one portfolio in view at a time.
  const portfolio = portfolios.data?.[0] ?? null;

  return (
    <div className="manual-holdings-tab">
      {portfolios.loading && <LoadingState />}
      {!portfolios.loading && portfolios.error && <ErrorState message={portfolios.error} onRetry={portfolios.retry} />}

      {!portfolios.loading && !portfolios.error && !portfolio && (
        <div className="portfolio-page__empty">
          <EmptyState message={t("portfolio.manual.noPortfolioYet")} />
          <button type="button" className="modal-button modal-button--primary" onClick={() => setModal({ kind: "create-portfolio" })}>
            {t("portfolio.forms.createPortfolio")}
          </button>
        </div>
      )}

      {!portfolios.loading && !portfolios.error && portfolio && (
        <>
          <section className="portfolio-page__header">
            <div>
              <h2 className="portfolio-page__name">{portfolio.name}</h2>
              {portfolio.description && <p className="portfolio-page__description">{portfolio.description}</p>}
            </div>
            <div className="portfolio-page__header-actions">
              <button type="button" className="modal-button" onClick={() => setModal({ kind: "rename-portfolio" })}>
                {t("portfolio.manual.rename")}
              </button>
              <button type="button" className="modal-button" onClick={() => setModal({ kind: "delete-portfolio" })}>
                {t("portfolio.manual.deletePortfolio")}
              </button>
            </div>
          </section>

          <PortfolioSummaryCards summary={portfolio.summary} />

          <section className="portfolio-page__holdings" aria-labelledby="holdings-heading">
            <div className="portfolio-page__holdings-header">
              <h2 id="holdings-heading">{t("portfolio.manual.holdings")}</h2>
              <button type="button" className="modal-button modal-button--primary" onClick={() => setModal({ kind: "add-holding" })}>
                {t("portfolio.forms.addHolding")}
              </button>
            </div>

            {portfolio.holdings.length === 0 ? (
              <EmptyState message={t("portfolio.manual.noHoldingsYet")} />
            ) : (
              <HoldingsTable
                holdings={portfolio.holdings}
                onEdit={(holding) => setModal({ kind: "edit-holding", holding })}
                onDelete={(holding) => setModal({ kind: "delete-holding", holding })}
              />
            )}
          </section>
        </>
      )}

      {modal.kind === "create-portfolio" && (
        <PortfolioFormModal
          onSubmit={async (body) => {
            await createPortfolio(body);
            portfolios.retry();
          }}
          onClose={closeModal}
        />
      )}

      {modal.kind === "rename-portfolio" && portfolio && (
        <PortfolioFormModal
          portfolio={portfolio}
          onSubmit={async (body) => {
            await updatePortfolio(portfolio.id, body);
            portfolios.retry();
          }}
          onClose={closeModal}
        />
      )}

      {modal.kind === "delete-portfolio" && portfolio && (
        <ConfirmDialog
          title={t("portfolio.manual.deletePortfolio")}
          message={t("portfolio.manual.deletePortfolioConfirm", { name: portfolio.name })}
          onConfirm={async () => {
            await deletePortfolio(portfolio.id);
            portfolios.retry();
          }}
          onClose={closeModal}
        />
      )}

      {modal.kind === "add-holding" && portfolio && (
        <HoldingFormModal
          onSubmit={async (values) => {
            await addHolding(portfolio.id, values);
            portfolios.retry();
          }}
          onClose={closeModal}
        />
      )}

      {modal.kind === "edit-holding" && (
        <HoldingFormModal
          holding={modal.holding}
          onSubmit={async (values) => {
            await updateHolding(modal.holding.id, values);
            portfolios.retry();
          }}
          onClose={closeModal}
        />
      )}

      {modal.kind === "delete-holding" && (
        <ConfirmDialog
          title={t("portfolio.manual.deleteHolding")}
          message={t("portfolio.manual.deleteHoldingConfirm", {
            name: modal.holding.coin_name ?? modal.holding.coin_symbol,
            symbol: modal.holding.coin_symbol,
          })}
          onConfirm={async () => {
            await deleteHolding(modal.holding.id);
            portfolios.retry();
          }}
          onClose={closeModal}
        />
      )}
    </div>
  );
}
