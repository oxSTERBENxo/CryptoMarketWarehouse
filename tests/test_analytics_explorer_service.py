import csv
import io
from datetime import date

import pytest

from analytics import explorer_service as service
from analytics.explorer_models import (
    ExplorerCondition,
    ExplorerFilters,
    ExplorerMetric,
    ExplorerRequest,
    ExplorerResultRow,
    ExplorerSortField,
    ExplorerSortOrder,
)


def _row(symbol: str, **overrides) -> ExplorerResultRow:
    base = {
        "coin_id": symbol.lower(),
        "symbol": symbol,
        "name": symbol.capitalize(),
        "image_url": None,
        "start_date": date(2026, 6, 1),
        "end_date": date(2026, 6, 30),
        "start_price": 100.0,
        "end_price": 110.0,
        "dollar_change": 10.0,
        "percent_change": 10.0,
        "low_price": 95.0,
        "high_price": 115.0,
        "avg_price": 105.0,
        "avg_volume": 1_000_000.0,
        "volatility_percent": 21.05,
        "start_rank": 10,
        "end_rank": 8,
        "rank_change": 2,
        "market_cap_usd": 50_000_000.0,
        "observation_count": 30,
    }
    base.update(overrides)
    return ExplorerResultRow.model_validate(base)


def _request(**overrides) -> ExplorerRequest:
    base = {
        "metric": ExplorerMetric.price,
        "condition": ExplorerCondition.increased_by_percent,
        "from_date": date(2026, 6, 1),
        "to_date": date(2026, 6, 30),
        "threshold": 5.0,
    }
    base.update(overrides)
    return ExplorerRequest.model_validate(base)


# ---------------------------------------------------------------------------
# Price change analyses
# ---------------------------------------------------------------------------


def test_price_increased_by_percent_keeps_only_rows_at_or_above_threshold():
    rows = [
        _row("BTC", percent_change=5.0),
        _row("ETH", percent_change=4.99),
        _row("SOL", percent_change=25.0),
        _row("XRP", percent_change=None),
    ]
    result = service.run_analysis(rows, _request(threshold=5.0))
    assert [r.symbol for r in result.rows] == ["SOL", "BTC"]
    assert result.analysis_label == "Price increased by at least X%"


def test_price_decreased_by_percent_uses_negative_changes():
    rows = [
        _row("BTC", percent_change=-12.0),
        _row("ETH", percent_change=-9.99),
        _row("SOL", percent_change=3.0),
    ]
    result = service.run_analysis(
        rows, _request(condition=ExplorerCondition.decreased_by_percent, threshold=10.0)
    )
    assert [r.symbol for r in result.rows] == ["BTC"]


def test_price_increased_by_amount_filters_on_dollar_change():
    rows = [
        _row("BTC", dollar_change=1500.0),
        _row("ETH", dollar_change=999.0),
        _row("SOL", dollar_change=1000.0),
    ]
    result = service.run_analysis(
        rows, _request(condition=ExplorerCondition.increased_by_amount, threshold=1000.0)
    )
    assert [r.symbol for r in result.rows] == ["BTC", "SOL"]


def test_price_decreased_by_amount_filters_on_negative_dollar_change():
    rows = [
        _row("BTC", dollar_change=-1500.0),
        _row("ETH", dollar_change=-500.0),
        _row("SOL", dollar_change=200.0),
    ]
    result = service.run_analysis(
        rows, _request(condition=ExplorerCondition.decreased_by_amount, threshold=1000.0)
    )
    assert [r.symbol for r in result.rows] == ["BTC"]


def test_top_gainers_and_losers_rank_by_percent_change():
    rows = [
        _row("BTC", percent_change=5.0),
        _row("ETH", percent_change=-8.0),
        _row("SOL", percent_change=20.0),
        _row("XRP", percent_change=None),
    ]
    gainers = service.run_analysis(rows, _request(condition=ExplorerCondition.top_n, threshold=None))
    losers = service.run_analysis(rows, _request(condition=ExplorerCondition.bottom_n, threshold=None))
    assert [r.symbol for r in gainers.rows] == ["SOL", "BTC", "ETH"]
    assert [r.symbol for r in losers.rows] == ["ETH", "BTC", "SOL"]


# ---------------------------------------------------------------------------
# Rank change analyses
# ---------------------------------------------------------------------------


def test_rank_improved_by_places():
    rows = [
        _row("BTC", rank_change=5),
        _row("ETH", rank_change=2),
        _row("SOL", rank_change=-4),
        _row("XRP", rank_change=None),
    ]
    result = service.run_analysis(
        rows,
        _request(metric=ExplorerMetric.market_cap_rank, condition=ExplorerCondition.improved_by, threshold=3.0),
    )
    assert [r.symbol for r in result.rows] == ["BTC"]


def test_rank_declined_by_places_sorted_worst_first():
    rows = [
        _row("BTC", rank_change=-5),
        _row("ETH", rank_change=-3),
        _row("SOL", rank_change=-2),
    ]
    result = service.run_analysis(
        rows,
        _request(metric=ExplorerMetric.market_cap_rank, condition=ExplorerCondition.declined_by, threshold=3.0),
    )
    assert [r.symbol for r in result.rows] == ["BTC", "ETH"]


# ---------------------------------------------------------------------------
# Volatility and volume analyses
# ---------------------------------------------------------------------------


def test_most_and_least_volatile_orderings():
    rows = [
        _row("BTC", volatility_percent=10.0),
        _row("ETH", volatility_percent=45.0),
        _row("SOL", volatility_percent=2.0),
        _row("XRP", volatility_percent=None),
    ]
    most = service.run_analysis(
        rows, _request(metric=ExplorerMetric.volatility, condition=ExplorerCondition.top_n, threshold=None)
    )
    least = service.run_analysis(
        rows, _request(metric=ExplorerMetric.volatility, condition=ExplorerCondition.bottom_n, threshold=None)
    )
    assert [r.symbol for r in most.rows] == ["ETH", "BTC", "SOL"]
    assert [r.symbol for r in least.rows] == ["SOL", "BTC", "ETH"]


def test_highest_average_volume_sorted_desc():
    rows = [
        _row("BTC", avg_volume=3_000_000.0),
        _row("ETH", avg_volume=9_000_000.0),
        _row("SOL", avg_volume=None),
    ]
    result = service.run_analysis(
        rows, _request(metric=ExplorerMetric.volume, condition=ExplorerCondition.top_n, threshold=None)
    )
    assert [r.symbol for r in result.rows] == ["ETH", "BTC"]


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_unsupported_combination_raises():
    with pytest.raises(service.UnsupportedAnalysisError):
        service.run_analysis(
            [], _request(metric=ExplorerMetric.volume, condition=ExplorerCondition.improved_by, threshold=1.0)
        )


def test_missing_required_threshold_raises():
    with pytest.raises(service.MissingThresholdError):
        service.run_analysis([_row("BTC")], _request(threshold=None))


# ---------------------------------------------------------------------------
# Optional value filters
# ---------------------------------------------------------------------------


def test_market_cap_and_volume_filters_apply_before_analysis():
    rows = [
        _row("BTC", market_cap_usd=100.0, avg_volume=10.0),
        _row("ETH", market_cap_usd=1000.0, avg_volume=500.0),
        _row("SOL", market_cap_usd=None, avg_volume=500.0),
    ]
    request = _request(
        threshold=0.0,
        filters=ExplorerFilters(min_market_cap=500.0, min_avg_volume=100.0),
    )
    result = service.run_analysis(rows, request)
    # SOL has an unknown market cap, so a market-cap bound excludes it.
    assert [r.symbol for r in result.rows] == ["ETH"]


def test_rank_range_and_price_range_filters():
    rows = [
        _row("BTC", end_rank=1, end_price=50_000.0),
        _row("ETH", end_rank=15, end_price=2_000.0),
        _row("SOL", end_rank=40, end_price=150.0),
    ]
    request = _request(
        threshold=0.0,
        filters=ExplorerFilters(min_rank=1, max_rank=20, min_price=1000.0, max_price=10_000.0),
    )
    result = service.run_analysis(rows, request)
    assert [r.symbol for r in result.rows] == ["ETH"]


# ---------------------------------------------------------------------------
# Sorting and pagination
# ---------------------------------------------------------------------------


def test_explicit_sort_overrides_analysis_default():
    rows = [
        _row("BTC", percent_change=5.0, market_cap_usd=900.0),
        _row("ETH", percent_change=20.0, market_cap_usd=100.0),
    ]
    result = service.run_analysis(
        rows,
        _request(threshold=0.0, sort_by=ExplorerSortField.market_cap, sort_order=ExplorerSortOrder.desc),
    )
    assert [r.symbol for r in result.rows] == ["BTC", "ETH"]
    assert result.sort_by is ExplorerSortField.market_cap


def test_rows_missing_the_sort_value_always_sort_last():
    rows = [
        _row("BTC", percent_change=5.0, avg_volume=None),
        _row("ETH", percent_change=10.0, avg_volume=100.0),
    ]
    ascending = service.run_analysis(
        rows,
        _request(threshold=0.0, sort_by=ExplorerSortField.avg_volume, sort_order=ExplorerSortOrder.asc),
    )
    assert [r.symbol for r in ascending.rows] == ["ETH", "BTC"]


def test_pagination_slices_rows_but_summary_covers_all_results():
    rows = [_row(f"C{i}", percent_change=float(i)) for i in range(1, 8)]
    result = service.run_analysis(rows, _request(threshold=0.0, limit=3, offset=3))
    # Default sort: percent_change desc -> 7,6,5 | 4,3,2 | 1
    assert [r.percent_change for r in result.rows] == [4.0, 3.0, 2.0]
    assert result.total_results == 7
    assert result.summary.results_found == 7
    assert result.summary.largest_increase_percent == 7.0
    assert result.summary.largest_decrease_percent == 1.0
    assert result.summary.average_percent_change == pytest.approx(4.0)


def test_offset_beyond_results_returns_empty_page():
    rows = [_row("BTC", percent_change=5.0)]
    result = service.run_analysis(rows, _request(threshold=0.0, offset=10))
    assert result.rows == []
    assert result.total_results == 1


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def test_summary_of_empty_results_is_all_none():
    result = service.run_analysis([], _request(threshold=0.0))
    summary = result.summary
    assert summary.results_found == 0
    assert summary.average_percent_change is None
    assert summary.largest_increase_percent is None
    assert summary.largest_increase_symbol is None
    assert summary.average_volume is None


def test_summary_names_the_extreme_movers():
    rows = [
        _row("BTC", percent_change=5.0, avg_volume=100.0),
        _row("ETH", percent_change=-2.0, avg_volume=300.0),
    ]
    result = service.run_analysis(rows, _request(condition=ExplorerCondition.top_n, threshold=None))
    assert result.summary.largest_increase_symbol == "BTC"
    assert result.summary.largest_decrease_symbol == "ETH"
    assert result.summary.average_volume == pytest.approx(200.0)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def test_rows_to_csv_has_header_and_one_line_per_row():
    rows = [_row("BTC"), _row("ETH", avg_volume=None)]
    csv_text = service.rows_to_csv(rows)
    lines = csv_text.strip().split("\n")
    assert len(lines) == 3
    assert lines[0].startswith("Symbol,Coin,Start Date,End Date,Start Price")
    assert lines[1].startswith("BTC,Btc,2026-06-01,2026-06-30,100.0,110.0,10.0,10.0")


def test_rows_to_csv_renders_unavailable_values_as_empty_cells():
    csv_text = service.rows_to_csv([_row("BTC", percent_change=None, avg_volume=None)])
    data_line = csv_text.strip().split("\n")[1]
    cells = data_line.split(",")
    header_cells = csv_text.strip().split("\n")[0].split(",")
    assert cells[header_cells.index("Percent Change")] == ""
    assert cells[header_cells.index("Average Volume (USD)")] == ""


@pytest.mark.parametrize("trigger", ["=", "+", "-", "@"])
def test_rows_to_csv_escapes_formula_trigger_characters_in_string_cells(trigger):
    """A coin name starting with =, +, -, or @ would otherwise be interpreted as a formula by
    Excel/Sheets/LibreOffice when the exported CSV is opened -- must be neutralized with a
    leading apostrophe so it renders as literal text instead."""
    csv_text = service.rows_to_csv([_row("BTC", name=f"{trigger}HYPERLINK(evil)")])
    data_row = list(csv.reader(io.StringIO(csv_text)))[1]
    header_row = list(csv.reader(io.StringIO(csv_text)))[0]

    assert data_row[header_row.index("Coin")] == f"'{trigger}HYPERLINK(evil)"


def test_rows_to_csv_does_not_escape_negative_numeric_values():
    """Only string cells get the formula-injection guard -- a numeric column's leading '-' for a
    negative number must remain a real number, not become escaped text."""
    csv_text = service.rows_to_csv([_row("BTC", dollar_change=-10.0, percent_change=-9.5)])
    data_line = csv_text.strip().split("\n")[1]
    cells = data_line.split(",")
    header_cells = csv_text.strip().split("\n")[0].split(",")
    assert cells[header_cells.index("Dollar Change (USD)")] == "-10.0"
    assert cells[header_cells.index("Percent Change")] == "-9.5"
