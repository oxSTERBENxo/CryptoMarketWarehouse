import { useEffect } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import "./Modal.css";

interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** Shared dialog shell for forms and confirmations: backdrop click and Escape both close it. */
export function Modal({ title, onClose, children }: ModalProps) {
  const { t } = useTranslation();
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="modal-title">{title}</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label={t("common.closeDialog")}>
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
