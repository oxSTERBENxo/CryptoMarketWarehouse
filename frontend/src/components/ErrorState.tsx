import { useTranslation } from "react-i18next";

interface ErrorStateProps {
  message: string;
  onRetry: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  const { t } = useTranslation();
  return (
    <div className="status-state status-state--error" role="alert">
      <p>{message}</p>
      <button type="button" onClick={onRetry} className="retry-button">
        {t("common.retry")}
      </button>
    </div>
  );
}
