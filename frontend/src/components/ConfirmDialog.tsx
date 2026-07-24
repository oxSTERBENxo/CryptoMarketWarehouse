import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Modal } from "./Modal";
import { ApiError } from "../api/client";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

export function ConfirmDialog({ title, message, confirmLabel, onConfirm, onClose }: ConfirmDialogProps) {
  const { t } = useTranslation();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("common.somethingWentWrong"));
      setSubmitting(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <div className="modal-form">
        <p>{message}</p>
        {error && <p className="modal-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="modal-button" onClick={onClose} disabled={submitting}>
            {t("common.cancel")}
          </button>
          <button type="button" className="modal-button modal-button--danger" onClick={handleConfirm} disabled={submitting}>
            {submitting ? t("common.deleting") : (confirmLabel ?? t("common.delete"))}
          </button>
        </div>
      </div>
    </Modal>
  );
}
