"""Cross-feature consistency checks: the same coin/period must produce the same percent-change
and volatility answer whether it's shown on the Dashboard/Market Leaders, the Analytics Explorer,
or the AI Coin Analysis card. The formula itself was already consistent everywhere (confirmed by
reading analytics_repository.py, analytics_explorer_repository.py, and ai_coin_analysis_service.py)
-- these tests exist to catch future drift between the two SQL copies of the formula, and to pin
down that the Python-side helper (metrics.safe_percent, used by ai_coin_analysis_service for
volatility) matches the SQL views' guarded semantics exactly (NULL/None on a zero base, not 0% or
an error)."""

import inspect
import re

from analytics import explorer_repository as analytics_explorer_repository
from analytics import repository as analytics_repository
from utils import metrics


def _extract_case_expr(source: str, alias: str) -> str:
    """Isolate the single 'CASE WHEN ... END AS {alias}' expression immediately preceding that
    alias, rather than the first CASE anywhere in the source -- both repository modules contain
    more than one CASE expression, so a naive first-match search can silently span the wrong one."""
    end_marker = f"END AS {alias}"
    end_idx = source.index(end_marker)
    start_idx = source.rindex("CASE WHEN", 0, end_idx)
    return " ".join(source[start_idx : end_idx + len(end_marker)].split())


def test_percent_change_sql_formula_matches_between_movers_and_explorer():
    """Market Leaders (analytics_repository._MOVER_FIELDS) and the Analytics Explorer
    (analytics_explorer_repository.fetch_period_stats) must use the identical percent_change SQL
    expression -- otherwise the same coin/period could show a different percent change on the two
    pages."""
    movers_source = analytics_repository._MOVER_FIELDS
    explorer_source = inspect.getsource(analytics_explorer_repository.fetch_period_stats)

    assert _extract_case_expr(movers_source, "percent_change") == _extract_case_expr(
        explorer_source, "percent_change"
    )


def test_volatility_sql_formula_matches_between_movers_and_explorer():
    movers_source = analytics_repository._MOVER_FIELDS
    explorer_source = inspect.getsource(analytics_explorer_repository.fetch_period_stats)

    assert _extract_case_expr(movers_source, "volatility_percent") == _extract_case_expr(
        explorer_source, "volatility_percent"
    )


def test_volatility_helper_matches_sql_case_guard_semantics():
    """ai_coin_analysis_service computes volatility in Python via metrics.safe_percent against the
    same period high/low the SQL views aggregate; it must behave identically to the SQL guard
    ('CASE WHEN low_price = 0 THEN NULL ELSE (high-low)/low*100 END') for every case, including the
    zero-low edge case."""

    def sql_case_volatility(high: float, low: float) -> float | None:
        if low == 0:
            return None
        return (high - low) / low * 100

    for high, low in [(120.0, 100.0), (100.0, 100.0), (50.0, 0.0), (200.0, 50.0)]:
        assert metrics.safe_percent(high - low, low) == sql_case_volatility(high, low)
