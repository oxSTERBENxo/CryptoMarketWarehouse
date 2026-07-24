import { useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Modal } from "./Modal";
import { ApiError } from "../api/client";
import type { Portfolio, PortfolioCreateRequest } from "../api/types";

interface PortfolioFormModalProps {
  /** Present when renaming/editing an existing portfolio; absent when creating one. */
  portfolio?: Portfolio;
  onSubmit: (body: PortfolioCreateRequest) => Promise<void>;
  onClose: () => void;
}

export function PortfolioFormModal({ portfolio, onSubmit, onClose }: PortfolioFormModalProps) {
  const { t } = useTranslation();
  const [name, setName] = useState(portfolio?.name ?? "");
  const [description, setDescription] = useState(portfolio?.description ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nameTouched, setNameTouched] = useState(false);

  const nameError = name.trim() === "" ? t("portfolio.forms.nameRequired") : null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setNameTouched(true);
    if (nameError) return;

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({ name: name.trim(), description: description.trim() || null });
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("common.somethingWentWrong"));
      setSubmitting(false);
    }
  }

  return (
    <Modal title={portfolio ? t("portfolio.forms.renamePortfolio") : t("portfolio.forms.createPortfolio")} onClose={onClose}>
      <form className="modal-form" onSubmit={handleSubmit}>
        <div className="modal-field">
          <label htmlFor="portfolio-name">{t("portfolio.forms.name")}</label>
          <input
            id="portfolio-name"
            type="text"
            value={name}
            maxLength={200}
            onChange={(event) => setName(event.target.value)}
            onBlur={() => setNameTouched(true)}
            autoFocus
          />
          {nameTouched && nameError && <span className="modal-field-error">{nameError}</span>}
        </div>
        <div className="modal-field">
          <label htmlFor="portfolio-description">{t("portfolio.forms.descriptionOptional")}</label>
          <textarea
            id="portfolio-description"
            value={description}
            maxLength={2000}
            rows={3}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
        {error && <p className="modal-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="modal-button" onClick={onClose} disabled={submitting}>
            {t("common.cancel")}
          </button>
          <button type="submit" className="modal-button modal-button--primary" disabled={submitting}>
            {submitting ? t("common.saving") : portfolio ? t("common.save") : t("common.create")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
