import type { ReactNode } from "react";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import { EmptyState } from "./EmptyState";

interface SectionStatusProps {
  loading: boolean;
  error: string | null;
  isEmpty: boolean;
  onRetry: () => void;
  emptyMessage?: string;
  children: ReactNode;
}

/** Renders the loading/error/empty state for a dashboard section, or its children once data is ready. */
export function SectionStatus({ loading, error, isEmpty, onRetry, emptyMessage, children }: SectionStatusProps) {
  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (isEmpty) return <EmptyState message={emptyMessage} />;
  return <>{children}</>;
}
