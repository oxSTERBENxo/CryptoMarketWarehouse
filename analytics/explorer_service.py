"""Analysis logic for the Analytics Explorer.

Each analysis is an independent predicate function registered in ANALYSES under its
(metric, condition) pair, rather than branches of one switch: adding a new analysis is one
function plus one registry entry, and every analysis automatically gets the shared filter /
sort / paginate / summarize pipeline in run_analysis(). All rows arrive pre-validated as
ExplorerResultRow (floats, not Decimals), so predicate and summary math stays in plain Python.
"""

import csv
import io
from dataclasses import dataclass
from typing import Callable

from analytics.explorer_models import (
    ExplorerCondition,
    ExplorerFilters,
    ExplorerMetric,
    ExplorerRequest,
    ExplorerResponse,
    ExplorerResultRow,
    ExplorerSortField,
    ExplorerSortOrder,
    ExplorerSummary,
)


class UnsupportedAnalysisError(ValueError):
    """The requested (metric, condition) pair has no registered analysis."""


class MissingThresholdError(ValueError):
    """The requested analysis needs a threshold but none was provided."""


# ---------------------------------------------------------------------------
# Analysis predicates: each decides whether one coin's period stats qualify.
# `threshold` is always a float for analyses registered with requires_threshold=True,
# and None for the top_n/bottom_n rankings (which qualify on data availability alone
# and let sorting + the result limit pick the N).
# ---------------------------------------------------------------------------


def price_increased_by_percent(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.percent_change is not None and row.percent_change >= threshold


def price_decreased_by_percent(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.percent_change is not None and row.percent_change <= -threshold


def price_increased_by_amount(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.dollar_change >= threshold


def price_decreased_by_amount(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.dollar_change <= -threshold


def highest_average_volume(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.avg_volume is not None


def rank_improved_by(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.rank_change is not None and row.rank_change >= threshold


def rank_declined_by(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.rank_change is not None and row.rank_change <= -threshold


def most_volatile(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.volatility_percent is not None


def least_volatile(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.volatility_percent is not None


def top_gainers(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.percent_change is not None


def top_losers(row: ExplorerResultRow, threshold: float | None) -> bool:
    return row.percent_change is not None


@dataclass(frozen=True)
class AnalysisSpec:
    label: str
    matches: Callable[[ExplorerResultRow, float | None], bool]
    requires_threshold: bool
    default_sort: ExplorerSortField
    default_order: ExplorerSortOrder


ANALYSES: dict[tuple[ExplorerMetric, ExplorerCondition], AnalysisSpec] = {
    (ExplorerMetric.price, ExplorerCondition.increased_by_percent): AnalysisSpec(
        "Price increased by at least X%",
        price_increased_by_percent,
        True,
        ExplorerSortField.percent_change,
        ExplorerSortOrder.desc,
    ),
    (ExplorerMetric.price, ExplorerCondition.decreased_by_percent): AnalysisSpec(
        "Price decreased by at least X%",
        price_decreased_by_percent,
        True,
        ExplorerSortField.percent_change,
        ExplorerSortOrder.asc,
    ),
    (ExplorerMetric.price, ExplorerCondition.increased_by_amount): AnalysisSpec(
        "Price increased by at least $X",
        price_increased_by_amount,
        True,
        ExplorerSortField.dollar_change,
        ExplorerSortOrder.desc,
    ),
    (ExplorerMetric.price, ExplorerCondition.decreased_by_amount): AnalysisSpec(
        "Price decreased by at least $X",
        price_decreased_by_amount,
        True,
        ExplorerSortField.dollar_change,
        ExplorerSortOrder.asc,
    ),
    (ExplorerMetric.price, ExplorerCondition.top_n): AnalysisSpec(
        "Top gainers",
        top_gainers,
        False,
        ExplorerSortField.percent_change,
        ExplorerSortOrder.desc,
    ),
    (ExplorerMetric.price, ExplorerCondition.bottom_n): AnalysisSpec(
        "Top losers",
        top_losers,
        False,
        ExplorerSortField.percent_change,
        ExplorerSortOrder.asc,
    ),
    (ExplorerMetric.volume, ExplorerCondition.top_n): AnalysisSpec(
        "Highest average trading volume",
        highest_average_volume,
        False,
        ExplorerSortField.avg_volume,
        ExplorerSortOrder.desc,
    ),
    (ExplorerMetric.market_cap_rank, ExplorerCondition.improved_by): AnalysisSpec(
        "Market-cap rank improved by at least X places",
        rank_improved_by,
        True,
        ExplorerSortField.rank_change,
        ExplorerSortOrder.desc,
    ),
    (ExplorerMetric.market_cap_rank, ExplorerCondition.declined_by): AnalysisSpec(
        "Market-cap rank declined by at least X places",
        rank_declined_by,
        True,
        ExplorerSortField.rank_change,
        ExplorerSortOrder.asc,
    ),
    (ExplorerMetric.volatility, ExplorerCondition.top_n): AnalysisSpec(
        "Most volatile coins",
        most_volatile,
        False,
        ExplorerSortField.volatility,
        ExplorerSortOrder.desc,
    ),
    (ExplorerMetric.volatility, ExplorerCondition.bottom_n): AnalysisSpec(
        "Least volatile coins",
        least_volatile,
        False,
        ExplorerSortField.volatility,
        ExplorerSortOrder.asc,
    ),
}


def spec_for(metric: ExplorerMetric, condition: ExplorerCondition) -> AnalysisSpec:
    try:
        return ANALYSES[(metric, condition)]
    except KeyError:
        supported = ", ".join(f"{m.value}+{c.value}" for m, c in sorted(ANALYSES, key=lambda k: (k[0].value, k[1].value)))
        raise UnsupportedAnalysisError(
            f"No analysis is defined for metric={metric.value!r} with condition={condition.value!r}. "
            f"Supported combinations: {supported}"
        ) from None


_SORT_ATTRS: dict[ExplorerSortField, str] = {
    ExplorerSortField.percent_change: "percent_change",
    ExplorerSortField.dollar_change: "dollar_change",
    ExplorerSortField.end_price: "end_price",
    ExplorerSortField.avg_volume: "avg_volume",
    ExplorerSortField.rank_change: "rank_change",
    ExplorerSortField.market_cap: "market_cap_usd",
    ExplorerSortField.volatility: "volatility_percent",
}


def passes_filters(row: ExplorerResultRow, filters: ExplorerFilters) -> bool:
    """Apply the optional value filters. A bound on a value the coin doesn't have (NULL in the
    warehouse) excludes the coin: an unknown value can't be shown to satisfy the bound."""
    checks: list[tuple[float | int | None, float | int | None, bool]] = [
        (filters.min_market_cap, row.market_cap_usd, True),
        (filters.max_market_cap, row.market_cap_usd, False),
        (filters.min_avg_volume, row.avg_volume, True),
        (filters.min_rank, row.end_rank, True),
        (filters.max_rank, row.end_rank, False),
        (filters.min_price, row.end_price, True),
        (filters.max_price, row.end_price, False),
    ]
    for bound, value, is_lower_bound in checks:
        if bound is None:
            continue
        if value is None:
            return False
        if is_lower_bound and value < bound:
            return False
        if not is_lower_bound and value > bound:
            return False
    return True


def sort_rows(
    rows: list[ExplorerResultRow], field: ExplorerSortField, order: ExplorerSortOrder
) -> list[ExplorerResultRow]:
    """Sort by one statistic; rows where that statistic is unavailable always sort last,
    regardless of direction, so a '—' never outranks a real value."""
    attr = _SORT_ATTRS[field]
    present = [r for r in rows if getattr(r, attr) is not None]
    absent = [r for r in rows if getattr(r, attr) is None]
    present.sort(key=lambda r: getattr(r, attr), reverse=(order is ExplorerSortOrder.desc))
    return present + absent


def summarize(rows: list[ExplorerResultRow]) -> ExplorerSummary:
    """Deterministic aggregates over every qualifying row (pre-pagination)."""
    changes = [(r.percent_change, r.symbol) for r in rows if r.percent_change is not None]
    volumes = [r.avg_volume for r in rows if r.avg_volume is not None]

    largest_increase = max(changes, key=lambda c: c[0]) if changes else None
    largest_decrease = min(changes, key=lambda c: c[0]) if changes else None

    return ExplorerSummary(
        results_found=len(rows),
        average_percent_change=(sum(c for c, _ in changes) / len(changes)) if changes else None,
        largest_increase_percent=largest_increase[0] if largest_increase else None,
        largest_increase_symbol=largest_increase[1] if largest_increase else None,
        largest_decrease_percent=largest_decrease[0] if largest_decrease else None,
        largest_decrease_symbol=largest_decrease[1] if largest_decrease else None,
        average_volume=(sum(volumes) / len(volumes)) if volumes else None,
    )


def run_analysis(rows: list[ExplorerResultRow], request: ExplorerRequest) -> ExplorerResponse:
    """Shared pipeline every analysis runs through: resolve the registered analysis, apply the
    optional value filters, apply the analysis predicate, sort, summarize over all qualifying
    rows, then paginate. Raises UnsupportedAnalysisError / MissingThresholdError for the route
    layer to convert into a 400."""
    spec = spec_for(request.metric, request.condition)
    if spec.requires_threshold and request.threshold is None:
        raise MissingThresholdError(f"The analysis {spec.label!r} requires a threshold.")

    qualifying = [
        row
        for row in rows
        if passes_filters(row, request.filters) and spec.matches(row, request.threshold)
    ]

    sort_by = request.sort_by if request.sort_by is not None else spec.default_sort
    sort_order = request.sort_order if request.sort_by is not None else spec.default_order
    ordered = sort_rows(qualifying, sort_by, sort_order)

    page = ordered[request.offset : request.offset + request.limit]

    return ExplorerResponse(
        analysis_label=spec.label,
        metric=request.metric,
        condition=request.condition,
        from_date=request.from_date,
        to_date=request.to_date,
        threshold=request.threshold,
        sort_by=sort_by,
        sort_order=sort_order,
        total_results=len(ordered),
        offset=request.offset,
        limit=request.limit,
        summary=summarize(ordered),
        rows=page,
    )


_CSV_COLUMNS: list[tuple[str, str]] = [
    ("symbol", "Symbol"),
    ("name", "Coin"),
    ("start_date", "Start Date"),
    ("end_date", "End Date"),
    ("start_price", "Start Price (USD)"),
    ("end_price", "End Price (USD)"),
    ("dollar_change", "Dollar Change (USD)"),
    ("percent_change", "Percent Change"),
    ("avg_price", "Average Price (USD)"),
    ("avg_volume", "Average Volume (USD)"),
    ("volatility_percent", "Volatility Percent"),
    ("start_rank", "Start Rank"),
    ("end_rank", "End Rank"),
    ("rank_change", "Rank Change"),
    ("market_cap_usd", "Market Cap (USD)"),
    ("observation_count", "Observations"),
]


# Spreadsheet apps (Excel, Google Sheets, LibreOffice) treat a cell starting with any of these
# characters as a formula, not text -- a coin symbol/name containing one (CoinGecko listings are
# not curated for this) would otherwise execute as a formula when the export is opened. Prefixing
# with a single quote is the standard mitigation: spreadsheet tools render it as literal text.
# Only applied to string cells -- numeric columns (e.g. dollar_change) legitimately start with "-"
# for negative values and must stay real numbers, not become escaped text.
_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@")


def _csv_safe(value):
    if isinstance(value, str) and value.startswith(_FORMULA_TRIGGER_CHARS):
        return "'" + value
    return value


def rows_to_csv(rows: list[ExplorerResultRow]) -> str:
    """Render result rows as CSV (header + one line per coin). Unavailable values are left as
    empty cells rather than a placeholder, so the file loads cleanly into spreadsheet tools."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([header for _, header in _CSV_COLUMNS])
    for row in rows:
        writer.writerow(
            ["" if (value := getattr(row, attr)) is None else _csv_safe(value) for attr, _ in _CSV_COLUMNS]
        )
    return buffer.getvalue()
