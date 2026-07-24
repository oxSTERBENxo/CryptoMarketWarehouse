import type { HealthCheck } from "../api/types";
import { HealthStatusBadge } from "./HealthStatusBadge";
import "./HealthCheckCard.css";

interface HealthCheckCardProps {
  title: string;
  check: HealthCheck;
}

/** One deterministic health check: a status badge plus the plain-English reason for it -- the
 * page never shows a bare status without explaining why, per the Warehouse Health requirements. */
export function HealthCheckCard({ title, check }: HealthCheckCardProps) {
  return (
    <div className="health-check-card">
      <div className="health-check-card__header">
        <h3>{title}</h3>
        <HealthStatusBadge status={check.status} />
      </div>
      <p className="health-check-card__message">{check.message}</p>
    </div>
  );
}
