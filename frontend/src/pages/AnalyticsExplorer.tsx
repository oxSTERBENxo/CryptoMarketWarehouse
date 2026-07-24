import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { exportExplorerCsv, runExplorerQuery } from "../api/explorer";
import type {
  ExplorerCondition,
  ExplorerFilters,
  ExplorerMetric,
  ExplorerRequest,
  ExplorerSortField,
} from "../api/types";
import { useApiData } from "../hooks/useApiData";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { ExplorerResultsTable } from "../components/ExplorerResultsTable";
import { analysesForMetric, findAnalysis, METRIC_OPTIONS, SORT_OPTIONS } from "../utils/explorerOptions";
import { formatCompactUsd, formatSignedPercent } from "../utils/format";
import "../components/OverviewCards.css";
import "../components/RangeSelector.css";
import "./AnalyticsExplorer.css";

function isoDaysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

/** Parses one optional numeric filter input: "" means "not set", anything else must be a number. */
function optionalNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  const parsed = Number(trimmed);
  return Number.isNaN(parsed) ? undefined : parsed;
}

const RESULT_LIMITS = [10, 25, 50, 100];

// Analytics Explorer's from_date/to_date are required fields (unlike Coin Details/Market Leaders,
// which can omit from_date to mean "all history"), so "All Available" resolves to a concrete date
// far earlier than this warehouse (or CoinGecko itself) could ever have data for -- the query then
// simply matches every real observation that exists, exactly like "all available" should.
const EARLIEST_POSSIBLE_DATE = "2009-01-03";
const DATE_PRESETS: { labelKey: string; days: number | "all" }[] = [
  { labelKey: "explorer.datePresets.7d", days: 7 },
  { labelKey: "explorer.datePresets.30d", days: 30 },
  { labelKey: "explorer.datePresets.90d", days: 90 },
  { labelKey: "explorer.datePresets.1y", days: 365 },
  { labelKey: "explorer.datePresets.allAvailable", days: "all" },
];

interface ExplorerFormValues {
  fromDate: string;
  toDate: string;
  metric: ExplorerMetric;
  condition: ExplorerCondition;
  threshold: string;
  sortBy: ExplorerSortField | "";
  sortOrder: "asc" | "desc";
  limit: number;
  minMarketCap: string;
  maxMarketCap: string;
  minAvgVolume: string;
  minRank: string;
  maxRank: string;
  minPrice: string;
  maxPrice: string;
}

function defaultFormValues(): ExplorerFormValues {
  return {
    fromDate: isoDaysAgo(30),
    toDate: new Date().toISOString().slice(0, 10),
    metric: "price",
    condition: "increased_by_percent",
    threshold: "5",
    sortBy: "",
    sortOrder: "desc",
    limit: 25,
    minMarketCap: "",
    maxMarketCap: "",
    minAvgVolume: "",
    minRank: "",
    maxRank: "",
    minPrice: "",
    maxPrice: "",
  };
}

interface RecentQuery {
  label: string;
  savedAt: string;
  form: ExplorerFormValues;
  request: ExplorerRequest;
}

interface SessionState {
  form: ExplorerFormValues;
  request: ExplorerRequest | null;
}

const RECENT_QUERIES_KEY = "explorer.recentQueries.v1";
const RECENT_QUERIES_LIMIT = 5;
const SESSION_STATE_KEY = "explorer.sessionState.v1";

function readJson<T>(storage: Storage, key: string): T | null {
  try {
    const raw = storage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeJson(storage: Storage, key: string, value: unknown): void {
  try {
    storage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage unavailable (private browsing quota, disabled storage, etc.) -- this is a
    // convenience feature only, never required for the page to function.
  }
}

function loadRecentQueries(): RecentQuery[] {
  return readJson<RecentQuery[]>(localStorage, RECENT_QUERIES_KEY) ?? [];
}

function saveRecentQuery(entry: RecentQuery): RecentQuery[] {
  const deduped = loadRecentQueries().filter((q) => JSON.stringify(q.request) !== JSON.stringify(entry.request));
  const next = [entry, ...deduped].slice(0, RECENT_QUERIES_LIMIT);
  writeJson(localStorage, RECENT_QUERIES_KEY, next);
  return next;
}

/** Mirrors the in-progress form and last-run request continuously, so navigating away (e.g.
 * drilling into a coin from the results table) and back with the browser Back button restores
 * exactly where the user left off, instead of a client-side route change resetting this page's
 * component state to its defaults. Session-scoped (not localStorage) since this is a continuity
 * convenience for the current tab, distinct from the user-visible Recent Queries history above. */
function loadSessionState(): SessionState | null {
  return readJson<SessionState>(sessionStorage, SESSION_STATE_KEY);
}

export function AnalyticsExplorer() {
  const { t } = useTranslation();
  const initial = useMemo(() => loadSessionState(), []);
  const initialForm = initial?.form ?? defaultFormValues();

  // Form state (what the user is editing). A run snapshots it into `request`; editing the form
  // never re-queries until Run Analysis is pressed again.
  const [fromDate, setFromDate] = useState(initialForm.fromDate);
  const [toDate, setToDate] = useState(initialForm.toDate);
  const [metric, setMetric] = useState<ExplorerMetric>(initialForm.metric);
  const [condition, setCondition] = useState<ExplorerCondition>(initialForm.condition);
  const [threshold, setThreshold] = useState(initialForm.threshold);
  const [sortBy, setSortBy] = useState<ExplorerSortField | "">(initialForm.sortBy);
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">(initialForm.sortOrder);
  const [limit, setLimit] = useState(initialForm.limit);
  const [minMarketCap, setMinMarketCap] = useState(initialForm.minMarketCap);
  const [maxMarketCap, setMaxMarketCap] = useState(initialForm.maxMarketCap);
  const [minAvgVolume, setMinAvgVolume] = useState(initialForm.minAvgVolume);
  const [minRank, setMinRank] = useState(initialForm.minRank);
  const [maxRank, setMaxRank] = useState(initialForm.maxRank);
  const [minPrice, setMinPrice] = useState(initialForm.minPrice);
  const [maxPrice, setMaxPrice] = useState(initialForm.maxPrice);
  const [formError, setFormError] = useState<string | null>(null);

  // The submitted request driving the current results. Sorting/pagination update it directly.
  const [request, setRequest] = useState<ExplorerRequest | null>(initial?.request ?? null);
  const results = useApiData(
    () => (request ? runExplorerQuery(request) : Promise.resolve(null)),
    [request]
  );

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [recentQueries, setRecentQueries] = useState<RecentQuery[]>(() => loadRecentQueries());

  useEffect(() => {
    writeJson(sessionStorage, SESSION_STATE_KEY, {
      form: {
        fromDate,
        toDate,
        metric,
        condition,
        threshold,
        sortBy,
        sortOrder,
        limit,
        minMarketCap,
        maxMarketCap,
        minAvgVolume,
        minRank,
        maxRank,
        minPrice,
        maxPrice,
      },
      request,
    } satisfies SessionState);
  }, [
    fromDate,
    toDate,
    metric,
    condition,
    threshold,
    sortBy,
    sortOrder,
    limit,
    minMarketCap,
    maxMarketCap,
    minAvgVolume,
    minRank,
    maxRank,
    minPrice,
    maxPrice,
    request,
  ]);

  const analysis = findAnalysis(metric, condition);
  const analysisOptions = analysesForMetric(metric);
  const needsThreshold = analysis?.thresholdLabelKey != null;
  const hasActiveFilters = [minMarketCap, maxMarketCap, minAvgVolume, minRank, maxRank, minPrice, maxPrice].some(
    (value) => value.trim() !== ""
  );

  const onMetricChange = (next: ExplorerMetric) => {
    setMetric(next);
    const first = analysesForMetric(next)[0];
    setCondition(first.condition);
  };

  const applyDatePreset = (days: number | "all") => {
    setToDate(new Date().toISOString().slice(0, 10));
    setFromDate(days === "all" ? EARLIEST_POSSIBLE_DATE : isoDaysAgo(days));
  };

  const onReset = () => {
    const defaults = defaultFormValues();
    setFromDate(defaults.fromDate);
    setToDate(defaults.toDate);
    setMetric(defaults.metric);
    setCondition(defaults.condition);
    setThreshold(defaults.threshold);
    setSortBy(defaults.sortBy);
    setSortOrder(defaults.sortOrder);
    setLimit(defaults.limit);
    setMinMarketCap(defaults.minMarketCap);
    setMaxMarketCap(defaults.maxMarketCap);
    setMinAvgVolume(defaults.minAvgVolume);
    setMinRank(defaults.minRank);
    setMaxRank(defaults.maxRank);
    setMinPrice(defaults.minPrice);
    setMaxPrice(defaults.maxPrice);
    setFormError(null);
    setExportError(null);
    setRequest(null);
  };

  const applyRecentQuery = (entry: RecentQuery) => {
    setFromDate(entry.form.fromDate);
    setToDate(entry.form.toDate);
    setMetric(entry.form.metric);
    setCondition(entry.form.condition);
    setThreshold(entry.form.threshold);
    setSortBy(entry.form.sortBy);
    setSortOrder(entry.form.sortOrder);
    setLimit(entry.form.limit);
    setMinMarketCap(entry.form.minMarketCap);
    setMaxMarketCap(entry.form.maxMarketCap);
    setMinAvgVolume(entry.form.minAvgVolume);
    setMinRank(entry.form.minRank);
    setMaxRank(entry.form.maxRank);
    setMinPrice(entry.form.minPrice);
    setMaxPrice(entry.form.maxPrice);
    setFormError(null);
    setExportError(null);
    setRequest({ ...entry.request, offset: 0 });
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);
    if (!fromDate || !toDate) {
      setFormError(t("explorer.errors.bothDatesRequired"));
      return;
    }
    if (fromDate > toDate) {
      setFormError(t("explorer.errors.fromAfterTo"));
      return;
    }
    const parsedThreshold = optionalNumber(threshold);
    if (needsThreshold && parsedThreshold === undefined) {
      setFormError(
        t("explorer.errors.thresholdRequired", {
          label: analysis?.thresholdLabelKey ? t(analysis.thresholdLabelKey) : "",
        })
      );
      return;
    }
    const filters: ExplorerFilters = {
      min_market_cap: optionalNumber(minMarketCap),
      max_market_cap: optionalNumber(maxMarketCap),
      min_avg_volume: optionalNumber(minAvgVolume),
      min_rank: optionalNumber(minRank),
      max_rank: optionalNumber(maxRank),
      min_price: optionalNumber(minPrice),
      max_price: optionalNumber(maxPrice),
    };
    const nextRequest: ExplorerRequest = {
      metric,
      condition,
      from_date: fromDate,
      to_date: toDate,
      threshold: needsThreshold ? parsedThreshold : null,
      filters,
      sort_by: sortBy === "" ? null : sortBy,
      sort_order: sortOrder,
      limit,
      offset: 0,
    };
    const analysisLabel = analysis ? t(analysis.labelKey) : metric;
    setExportError(null);
    setRequest(nextRequest);
    setRecentQueries(
      saveRecentQuery({
        label: `${analysisLabel} · ${fromDate} → ${toDate}`,
        savedAt: new Date().toISOString(),
        form: {
          fromDate,
          toDate,
          metric,
          condition,
          threshold,
          sortBy,
          sortOrder,
          limit,
          minMarketCap,
          maxMarketCap,
          minAvgVolume,
          minRank,
          maxRank,
          minPrice,
          maxPrice,
        },
        request: nextRequest,
      })
    );
  };

  const onSortChange = (field: ExplorerSortField) => {
    setRequest((prev) => {
      if (!prev) return prev;
      const currentField = results.data?.sort_by;
      const currentOrder = results.data?.sort_order ?? "desc";
      const nextOrder = currentField === field && currentOrder === "desc" ? "asc" : "desc";
      return { ...prev, sort_by: field, sort_order: nextOrder, offset: 0 };
    });
  };

  const onPageChange = (offset: number) => {
    setRequest((prev) => (prev ? { ...prev, offset } : prev));
  };

  const onExport = async () => {
    if (!request) return;
    setExporting(true);
    setExportError(null);
    try {
      const { csv, filename } = await exportExplorerCsv(request);
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : t("explorer.errors.exportFailed"));
    } finally {
      setExporting(false);
    }
  };

  const data = results.data;

  return (
    <main className="explorer">
      <div className="explorer__header">
        <div>
          <h1 className="explorer__title">{t("explorer.title")}</h1>
          <p className="explorer__subtitle">{t("explorer.subtitle")}</p>
        </div>
      </div>

      {recentQueries.length > 0 && (
        <div className="explorer__recent-queries">
          <span className="explorer__recent-queries-label">{t("explorer.recent")}</span>
          {recentQueries.map((entry, index) => (
            <button
              key={`${entry.savedAt}-${index}`}
              type="button"
              className="explorer__recent-query-chip"
              onClick={() => applyRecentQuery(entry)}
            >
              {entry.label}
            </button>
          ))}
        </div>
      )}

      <form className="explorer__form" onSubmit={onSubmit} aria-label={t("explorer.formLabel")}>
        <div className="range-selector explorer__presets" role="group" aria-label={t("explorer.datePresetsLabel")}>
          {DATE_PRESETS.map((preset) => (
            <button
              key={preset.labelKey}
              type="button"
              className="range-selector__option"
              onClick={() => applyDatePreset(preset.days)}
            >
              {t(preset.labelKey)}
            </button>
          ))}
        </div>

        <div className="explorer__form-grid">
          <label className="explorer__field">
            <span>{t("explorer.fields.from")}</span>
            <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} required />
          </label>
          <label className="explorer__field">
            <span>{t("explorer.fields.to")}</span>
            <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} required />
          </label>
          <label className="explorer__field">
            <span>{t("explorer.fields.metric")}</span>
            <select value={metric} onChange={(e) => onMetricChange(e.target.value as ExplorerMetric)}>
              {METRIC_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {t(option.labelKey)}
                </option>
              ))}
            </select>
          </label>
          <label className="explorer__field">
            <span>{t("explorer.fields.analysisType")}</span>
            <select value={condition} onChange={(e) => setCondition(e.target.value as ExplorerCondition)}>
              {analysisOptions.map((option) => (
                <option key={option.condition} value={option.condition}>
                  {t(option.labelKey)}
                </option>
              ))}
            </select>
          </label>
          {needsThreshold && (
            <label className="explorer__field">
              <span>{analysis?.thresholdLabelKey ? t(analysis.thresholdLabelKey) : ""}</span>
              <input
                type="number"
                step="any"
                min="0"
                value={threshold}
                placeholder={analysis?.thresholdPlaceholderKey ? t(analysis.thresholdPlaceholderKey) : undefined}
                onChange={(e) => setThreshold(e.target.value)}
              />
            </label>
          )}
          <label className="explorer__field">
            <span>{t("explorer.fields.sortBy")}</span>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as ExplorerSortField | "")}>
              <option value="">{t("explorer.fields.analysisDefault")}</option>
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {t(option.labelKey)}
                </option>
              ))}
            </select>
          </label>
          <label className="explorer__field">
            <span>{t("explorer.fields.direction")}</span>
            <select value={sortOrder} onChange={(e) => setSortOrder(e.target.value as "asc" | "desc")}>
              <option value="desc">{t("explorer.fields.descending")}</option>
              <option value="asc">{t("explorer.fields.ascending")}</option>
            </select>
          </label>
          <label className="explorer__field">
            <span>{t("explorer.fields.resultsPerPage")}</span>
            <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
              {RESULT_LIMITS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>

        <details className="explorer__filters">
          <summary>{t("explorer.filters.summary")}</summary>
          <div className="explorer__form-grid">
            <label className="explorer__field">
              <span>{t("explorer.filters.minMarketCap")}</span>
              <input type="number" min="0" step="any" value={minMarketCap} onChange={(e) => setMinMarketCap(e.target.value)} />
            </label>
            <label className="explorer__field">
              <span>{t("explorer.filters.maxMarketCap")}</span>
              <input type="number" min="0" step="any" value={maxMarketCap} onChange={(e) => setMaxMarketCap(e.target.value)} />
            </label>
            <label className="explorer__field">
              <span>{t("explorer.filters.minAvgVolume")}</span>
              <input type="number" min="0" step="any" value={minAvgVolume} onChange={(e) => setMinAvgVolume(e.target.value)} />
            </label>
            <label className="explorer__field">
              <span>{t("explorer.filters.minRank")}</span>
              <input type="number" min="1" step="1" value={minRank} onChange={(e) => setMinRank(e.target.value)} />
            </label>
            <label className="explorer__field">
              <span>{t("explorer.filters.maxRank")}</span>
              <input type="number" min="1" step="1" value={maxRank} onChange={(e) => setMaxRank(e.target.value)} />
            </label>
            <label className="explorer__field">
              <span>{t("explorer.filters.minPrice")}</span>
              <input type="number" min="0" step="any" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} />
            </label>
            <label className="explorer__field">
              <span>{t("explorer.filters.maxPrice")}</span>
              <input type="number" min="0" step="any" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} />
            </label>
          </div>
        </details>

        <div className="explorer__actions">
          <button type="submit" className="explorer__run-button" disabled={results.loading && request !== null}>
            {results.loading && request !== null ? t("explorer.actions.running") : t("explorer.actions.runAnalysis")}
          </button>
          <button type="button" className="explorer__reset-button" onClick={onReset}>
            {t("explorer.actions.resetFilters")}
          </button>
          {data && data.total_results > 0 && (
            <button type="button" className="explorer__export-button" onClick={onExport} disabled={exporting}>
              {exporting ? t("explorer.actions.exporting") : t("explorer.actions.exportCsv")}
            </button>
          )}
        </div>
        {formError && (
          <p className="explorer__form-error" role="alert">
            {formError}
          </p>
        )}
        {exportError && (
          <p className="explorer__form-error" role="alert">
            {exportError}
          </p>
        )}
      </form>

      {request === null && <EmptyState message={t("explorer.emptyBeforeRun")} />}

      {request !== null && results.loading && <LoadingState label={t("explorer.loadingRun")} />}
      {request !== null && !results.loading && results.error && (
        <ErrorState message={results.error} onRetry={results.retry} />
      )}

      {request !== null && !results.loading && !results.error && data && (
        <>
          <p className="explorer__result-caption">
            {analysis ? t(analysis.labelKey) : data.analysis_label} · {data.from_date} → {data.to_date}
          </p>

          <dl className="overview-grid explorer__summary-grid">
            <div className="overview-card">
              <dt>{t("explorer.summary.resultsFound")}</dt>
              <dd>{data.summary.results_found}</dd>
            </div>
            <div className="overview-card">
              <dt>{t("explorer.summary.averageChange")}</dt>
              <dd>{formatSignedPercent(data.summary.average_percent_change)}</dd>
            </div>
            <div className="overview-card">
              <dt>{t("explorer.summary.largestIncrease")}</dt>
              <dd>
                {formatSignedPercent(data.summary.largest_increase_percent)}
                {data.summary.largest_increase_symbol && (
                  <span className="explorer__summary-symbol">{data.summary.largest_increase_symbol.toUpperCase()}</span>
                )}
              </dd>
            </div>
            <div className="overview-card">
              <dt>{t("explorer.summary.largestDecrease")}</dt>
              <dd>
                {formatSignedPercent(data.summary.largest_decrease_percent)}
                {data.summary.largest_decrease_symbol && (
                  <span className="explorer__summary-symbol">{data.summary.largest_decrease_symbol.toUpperCase()}</span>
                )}
              </dd>
            </div>
            <div className="overview-card">
              <dt>{t("explorer.summary.averageVolume")}</dt>
              <dd>{formatCompactUsd(data.summary.average_volume)}</dd>
            </div>
          </dl>

          {data.total_results === 0 ? (
            <EmptyState
              message={hasActiveFilters ? t("explorer.emptyWithFilters") : t("explorer.emptyNoFilters")}
            />
          ) : (
            <ExplorerResultsTable
              rows={data.rows}
              sortBy={data.sort_by}
              sortOrder={data.sort_order}
              onSortChange={onSortChange}
              offset={data.offset}
              limit={data.limit}
              totalResults={data.total_results}
              onPageChange={onPageChange}
              fromDate={data.from_date}
              toDate={data.to_date}
            />
          )}
        </>
      )}
    </main>
  );
}
