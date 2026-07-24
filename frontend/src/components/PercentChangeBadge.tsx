import { changeArrow, changeClass, formatSignedPercent } from "../utils/format";
import "./PercentChangeBadge.css";

interface PercentChangeBadgeProps {
  value: number | null | undefined;
  className?: string;
}

/** Consistent 24h/period change display reused by every coin table and picker (Parts 1/3):
 * "▲ +1.84%" in green, "▼ -2.31%" in red, "0.00%" muted, "—" when unavailable. */
export function PercentChangeBadge({ value, className }: PercentChangeBadgeProps) {
  const arrow = changeArrow(value);
  return (
    <span className={`percent-change-badge ${changeClass(value)}${className ? ` ${className}` : ""}`}>
      {arrow && <span aria-hidden="true">{arrow} </span>}
      {formatSignedPercent(value)}
    </span>
  );
}
