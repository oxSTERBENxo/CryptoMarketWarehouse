import { useTranslation } from "react-i18next";
import { RANGE_OPTIONS } from "../utils/dateRange";
import type { RangeOption } from "../utils/dateRange";
import "./RangeSelector.css";

interface RangeSelectorProps<T extends string> {
  value: T;
  onChange: (range: T) => void;
  /** Defaults to the full RANGE_OPTIONS (used by Coin Details). Pass a narrower list (e.g.
   * LEADERS_RANGE_OPTIONS) for callers that don't support every option. */
  options?: { value: T; label: string }[];
}

export function RangeSelector<T extends string = RangeOption>({
  value,
  onChange,
  options,
}: RangeSelectorProps<T>) {
  const { t } = useTranslation();
  const resolvedOptions = options ?? (RANGE_OPTIONS as unknown as { value: T; label: string }[]);
  return (
    <div className="range-selector" role="group" aria-label={t("common.selectDateRange")}>
      {resolvedOptions.map((option) => {
        const active = option.value === value;
        // "Today"/"All" are real words worth translating; the "7D"/"30D"/"90D"/"1Y" compact
        // codes are short, widely-recognized abbreviations left as-is in both languages.
        const label =
          option.value === "today" ? t("dateRange.today") : option.value === "all" ? t("dateRange.all") : option.label;
        return (
          <button
            key={option.value}
            type="button"
            className="range-selector__option"
            aria-pressed={active}
            data-active={active}
            onClick={() => onChange(option.value)}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
