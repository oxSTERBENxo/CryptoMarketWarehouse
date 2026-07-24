import { useTranslation } from "react-i18next";

interface EmptyStateProps {
  message?: string;
}

export function EmptyState({ message }: EmptyStateProps) {
  const { t } = useTranslation();
  return (
    <div className="status-state status-state--empty">
      <p>{message ?? t("common.noData")}</p>
    </div>
  );
}
