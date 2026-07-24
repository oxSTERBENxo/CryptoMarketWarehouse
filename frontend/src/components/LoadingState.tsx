import { useTranslation } from "react-i18next";

interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label }: LoadingStateProps) {
  const { t } = useTranslation();
  return (
    <div className="status-state status-state--loading" role="status" aria-live="polite">
      <span className="status-spinner" aria-hidden="true" />
      <span>{label ?? t("common.loading")}</span>
    </div>
  );
}
