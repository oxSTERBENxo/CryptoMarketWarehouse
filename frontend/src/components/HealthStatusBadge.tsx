import type { HealthState } from "../api/types";
import "./HealthStatusBadge.css";

const LABELS: Record<HealthState, string> = {
  healthy: "Healthy",
  warning: "Warning",
  error: "Error",
  unknown: "Unknown",
};

/** Small pill for one HealthState (healthy/warning/error/unknown), reused across every
 * Warehouse Health status card so the same status always looks the same. */
export function HealthStatusBadge({ status }: { status: HealthState }) {
  return <span className={`health-status-badge health-status-badge--${status}`}>{LABELS[status]}</span>;
}
