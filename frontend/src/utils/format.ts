import i18n from "../i18n";

const PLACEHOLDER = "—"; // em dash, for null/unavailable values

/** BCP 47 locale for every Intl.NumberFormat/DateTimeFormat call in this module, derived from the
 * active UI language so numbers and dates follow the selected locale (en -> en-US, mk -> mk-MK).
 * Components re-render on language change via their useTranslation() subscription, so re-invoking
 * these formatters picks up the new locale automatically. */
function currentLocale(): string {
  return i18n.language === "mk" ? "mk-MK" : "en-US";
}

function isUsable(value: number | null | undefined): value is number {
  return typeof value === "number" && !Number.isNaN(value);
}

/** Standard USD currency formatting, e.g. $67,420.15. Returns a placeholder for null/NaN. */
export function formatUsd(value: number | null | undefined): string {
  if (!isUsable(value)) return PLACEHOLDER;
  return new Intl.NumberFormat(currentLocale(), {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/** Large-value USD formatting with compact suffixes, e.g. $2.14T, $99.35B. Returns a placeholder for null/NaN. */
export function formatCompactUsd(value: number | null | undefined): string {
  if (!isUsable(value)) return PLACEHOLDER;
  return new Intl.NumberFormat(currentLocale(), {
    style: "currency",
    currency: "USD",
    notation: "compact",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Cryptocurrency price formatting. Prices >= $1 use standard 2-decimal currency formatting.
 * Prices between $0.01 and $1 use 4 decimals. Prices below $0.01 scale decimal places to the
 * value's magnitude so small prices (e.g. $0.000042) remain legible instead of rounding to $0.00.
 */
export function formatCryptoPrice(value: number | null | undefined): string {
  if (!isUsable(value)) return PLACEHOLDER;
  const abs = Math.abs(value);

  if (abs === 0) return formatUsd(0);
  if (abs >= 1) return formatUsd(value);

  let decimals: number;
  if (abs >= 0.01) {
    decimals = 4;
  } else {
    decimals = Math.min(10, -Math.floor(Math.log10(abs)) + 1);
  }

  return new Intl.NumberFormat(currentLocale(), {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/** Formats an ISO date string (e.g. "2026-07-22") as a readable date, e.g. "Jul 22, 2026". */
export function formatDate(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  return new Intl.DateTimeFormat(currentLocale(), {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

/** Plain integer formatting with thousands separators, e.g. 20 coins tracked -> "20". */
export function formatNumber(value: number | null | undefined): string {
  if (!isUsable(value)) return PLACEHOLDER;
  return new Intl.NumberFormat(currentLocale()).format(value);
}

/** Formats an ISO datetime string (date + time) as e.g. "Jul 22, 2026, 3:45 PM". Returns a placeholder for null/invalid. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  return new Intl.DateTimeFormat(currentLocale(), {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

/** Formats an ISO datetime string as a date only, e.g. "Jul 22, 2026" — unlike formatDate(), which
 * expects a bare "YYYY-MM-DD" date string, this accepts a full timestamp (as returned by
 * coverage.earliest_observation/latest_observation) and drops the time. */
export function formatIsoDate(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  return new Intl.DateTimeFormat(currentLocale(), {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

/** Short axis-tick date with no year, e.g. "Jul 22" — for chart X axes where formatDate() is too wide. */
export function formatChartAxisDate(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  return new Intl.DateTimeFormat(currentLocale(), { month: "short", day: "numeric" }).format(date);
}

/** Hour:minute formatting for an ISO timestamp, e.g. "09:00", "16:30" — intraday chart axis/tooltip labels. */
export function formatTime(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  return new Intl.DateTimeFormat(currentLocale(), { hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

/** Signed USD formatting for profit/loss figures, e.g. "+$1,234.56" / "-$1,234.56". Returns a placeholder for null/NaN. */
export function formatSignedUsd(value: number | null | undefined): string {
  if (!isUsable(value)) return PLACEHOLDER;
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${formatUsd(Math.abs(value))}`;
}

/** Signed percentage formatting, e.g. "+12.34%" / "-5.00%". Returns a placeholder for null/NaN. */
export function formatSignedPercent(value: number | null | undefined): string {
  if (!isUsable(value)) return PLACEHOLDER;
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${Math.abs(value).toFixed(2)}%`;
}

/** CoinGecko market-cap rank formatting for chart axes/tooltips, e.g. "#1". */
export function formatRank(value: number | null | undefined): string {
  if (!isUsable(value)) return PLACEHOLDER;
  return `#${value}`;
}

/** Shared sign classification for any signed metric (24h change, profit/loss, ...): "positive"
 * for > 0, "negative" for < 0, "neutral" for exactly 0 or unavailable. Backs the `profit-positive`
 * / `profit-negative` / `profit-neutral` classes already used across Portfolio, Paper Trading,
 * Market Leaders, and Coin Details, so every consumer stays visually consistent. */
export function changeDirection(value: number | null | undefined): "positive" | "negative" | "neutral" {
  if (!isUsable(value) || value === 0) return "neutral";
  return value > 0 ? "positive" : "negative";
}

/** `profit-positive` / `profit-negative` / `profit-neutral` class name for a signed value. */
export function changeClass(value: number | null | undefined): string {
  return `profit-${changeDirection(value)}`;
}

/** "▲" / "▼" for a strictly positive/negative value, or null when zero/unavailable (no arrow is
 * shown for "0.00%" or "—", per the 24h-change display rules). */
export function changeArrow(value: number | null | undefined): "▲" | "▼" | null {
  const direction = changeDirection(value);
  if (direction === "positive") return "▲";
  if (direction === "negative") return "▼";
  return null;
}
