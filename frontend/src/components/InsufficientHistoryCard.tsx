import { useTranslation } from "react-i18next";
import { formatCryptoPrice } from "../utils/format";
import "./InsufficientHistoryCard.css";

interface InsufficientHistoryCardProps {
  price: number;
  /** Pre-formatted date or time label for the one point on record, e.g. "Jul 22, 2026" or "14:35". */
  label: string;
  observationCount: number;
  /** Overrides the default explanatory note (daily wording) -- e.g. for the intraday case. */
  note?: string;
}

/** Compact stand-in for a chart when there's too little history to plot a trend (0-1 usable
 * points) — shows the one data point that does exist instead of a mostly-empty chart canvas. */
export function InsufficientHistoryCard({ price, label, observationCount, note }: InsufficientHistoryCardProps) {
  const { t } = useTranslation();
  const moreNeeded = Math.max(2 - observationCount, 1);
  const defaultNote = t("coinDetails.insufficientHistory.note", { count: moreNeeded });

  return (
    <div className="insufficient-history">
      <div className="insufficient-history__point">
        <span className="insufficient-history__label">{t("coinDetails.insufficientHistory.onlyObservation")}</span>
        <span className="insufficient-history__price">{formatCryptoPrice(price)}</span>
        <span className="insufficient-history__date">{label}</span>
      </div>
      <p className="insufficient-history__note">{note ?? defaultNote}</p>
    </div>
  );
}
