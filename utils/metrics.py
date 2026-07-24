"""Shared percent-change/ratio helpers, so the guard against a zero or missing denominator is
defined once instead of re-implemented (with subtly different guard conventions -- some checked
`denominator == 0`, some checked truthiness, some `> 0`) across ai/coin_analysis_service.py,
portfolio/service.py, and paper_trading/service.py. The core formula was already consistent
everywhere it appeared; this only consolidates the edge-case handling.

Works with both float and Decimal operands (paper_trading_service does all its money math in
Decimal), since both support the same arithmetic and equality operators used here.
"""

from decimal import Decimal

Number = float | Decimal


def safe_percent(numerator: Number | None, denominator: Number | None) -> Number | None:
    """numerator / denominator * 100, or None if either operand is unknown or denominator is
    exactly zero (a ratio against zero is undefined, never reported as 0% or infinite)."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator * 100


def percent_change(start: Number | None, end: Number | None) -> Number | None:
    """(end - start) / start * 100, or None if either value is unknown or start is exactly zero
    (a percent change against a zero base is undefined)."""
    if start is None or end is None:
        return None
    return safe_percent(end - start, start)
