import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getCurrentMarket } from "../api/analytics";
import { useApiData } from "../hooks/useApiData";
import { CoinLogo } from "./CoinLogo";
import { PercentChangeBadge } from "./PercentChangeBadge";
import { formatCryptoPrice } from "../utils/format";
import "./CoinSelect.css";

interface CoinOption {
  symbol: string;
  name: string;
  image_url: string | null;
  price_usd: number;
  price_change_percentage_24h: number | null;
  market_cap_rank: number | null;
}

interface CoinSelectProps {
  value: string;
  onChange: (symbol: string) => void;
  disabled?: boolean;
  /** When present, only these symbols are offered (e.g. Sell: only currently-held coins). */
  restrictToSymbols?: string[];
}

// Generous over the scheduler's current top-100 tracking limit, so the dropdown always covers
// every coin that could plausibly have live market data (backend caps this at 500).
const FETCH_LIMIT = 500;

function sortOptions(options: CoinOption[]): CoinOption[] {
  const ranked = options.filter((o) => o.market_cap_rank != null).sort((a, b) => a.market_cap_rank! - b.market_cap_rank!);
  const unranked = options
    .filter((o) => o.market_cap_rank == null)
    .sort((a, b) => a.name.localeCompare(b.name));
  return [...ranked, ...unranked];
}

/** Searchable coin dropdown sourced from the warehouse's live current-market data (Part 1/6) --
 * every row shows the coin's logo, name, symbol, current price, and 24h change, sorted by
 * CoinGecko market-cap rank ascending, then unranked coins alphabetically. Each option is a
 * single full-width `<button>`, so clicking anywhere in the row (including the logo or blank
 * padding) selects the coin with no nested/duplicated handlers, and native button semantics
 * already give Enter/Space selection for free. */
export function CoinSelect({ value, onChange, disabled, restrictToSymbols }: CoinSelectProps) {
  const { t } = useTranslation();
  const coins = useApiData(() => getCurrentMarket(FETCH_LIMIT));
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const restrictSet = useMemo(
    () => (restrictToSymbols ? new Set(restrictToSymbols.map((s) => s.toUpperCase())) : null),
    [restrictToSymbols]
  );

  const options = useMemo<CoinOption[]>(() => {
    const list = coins.data?.coins ?? [];
    const mapped = list
      .filter((c) => !restrictSet || restrictSet.has(c.symbol.toUpperCase()))
      .map((c) => ({
        symbol: c.symbol.toUpperCase(),
        name: c.name,
        image_url: c.image_url,
        price_usd: c.price_usd,
        price_change_percentage_24h: c.price_change_percentage_24h,
        market_cap_rank: c.market_cap_rank,
      }));
    return sortOptions(mapped);
  }, [coins.data, restrictSet]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.name.toLowerCase().includes(q) || o.symbol.toLowerCase().includes(q));
  }, [options, query]);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const selected = options.find((o) => o.symbol === value);

  function selectOption(symbol: string) {
    onChange(symbol);
    setQuery("");
    setOpen(false);
  }

  return (
    <div className="coin-select" ref={containerRef}>
      <input
        type="text"
        placeholder={coins.loading ? t("coinSelect.loading") : t("coinSelect.searchPlaceholder")}
        value={open ? query : selected ? `${selected.name} (${selected.symbol})` : ""}
        disabled={disabled || coins.loading}
        onFocus={() => {
          setQuery("");
          setOpen(true);
        }}
        onChange={(event) => setQuery(event.target.value)}
        role="combobox"
        aria-expanded={open}
        aria-controls="coin-select-listbox"
      />
      {open && !disabled && (
        <ul className="coin-select__options" role="listbox" id="coin-select-listbox">
          {coins.error && <li className="coin-select__status">{coins.error}</li>}
          {!coins.error && filtered.length === 0 && (
            <li className="coin-select__status">{t("coinSelect.noMatches")}</li>
          )}
          {filtered.map((option) => (
            <li key={option.symbol}>
              <button
                type="button"
                role="option"
                aria-selected={option.symbol === value}
                className={`coin-select__option${option.symbol === value ? " coin-select__option--selected" : ""}`}
                onClick={() => selectOption(option.symbol)}
                onKeyDown={(event) => {
                  // Native <button> default-action semantics already turn Enter/Space into a
                  // click; prevent that default here and select exactly once ourselves, so
                  // there's never a double-selection from the native click plus this handler.
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    selectOption(option.symbol);
                  }
                }}
              >
                <CoinLogo src={option.image_url} name={option.name} size={28} />
                <span className="coin-select__option-identity">
                  <span className="coin-select__option-name">{option.name}</span>
                  <span className="coin-select__option-symbol">{option.symbol}</span>
                </span>
                <span className="coin-select__option-price">
                  <span>{formatCryptoPrice(option.price_usd)}</span>
                  <PercentChangeBadge value={option.price_change_percentage_24h} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
