from decimal import Decimal

from utils import metrics


def test_safe_percent_computes_ratio():
    assert metrics.safe_percent(50.0, 200.0) == 25.0


def test_safe_percent_none_on_zero_denominator():
    assert metrics.safe_percent(50.0, 0.0) is None


def test_safe_percent_none_on_missing_operands():
    assert metrics.safe_percent(None, 200.0) is None
    assert metrics.safe_percent(50.0, None) is None


def test_safe_percent_supports_decimal():
    result = metrics.safe_percent(Decimal("50"), Decimal("200"))
    assert result == Decimal("25")


def test_safe_percent_allows_negative_numerator():
    """A loss (negative numerator) must still compute a real negative percentage, not None."""
    assert metrics.safe_percent(-50.0, 200.0) == -25.0


def test_percent_change_computes_increase():
    assert metrics.percent_change(100.0, 110.0) == 10.0


def test_percent_change_computes_decrease():
    assert metrics.percent_change(100.0, 90.0) == -10.0


def test_percent_change_none_on_zero_start():
    assert metrics.percent_change(0.0, 50.0) is None


def test_percent_change_none_on_missing_operands():
    assert metrics.percent_change(None, 110.0) is None
    assert metrics.percent_change(100.0, None) is None
