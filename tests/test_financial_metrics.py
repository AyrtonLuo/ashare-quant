"""
test_financial_metrics.py — Tests for Deterministic Financial Metrics Calculator.
"""

from src.data.fundamentals.metrics.calculator import FinancialMetricsCalculator


def test_calculate_pe_lyr_positive():
    pe, status = FinancialMetricsCalculator.calculate_pe_lyr(price=100.0, eps_annual=5.0)
    assert pe == 20.0
    assert status == "VALID"


def test_calculate_pe_lyr_negative_eps():
    """Negative EPS must return None and NOT_MEANINGFUL (Never 0 or dummy multiplier)."""
    pe, status = FinancialMetricsCalculator.calculate_pe_lyr(price=100.0, eps_annual=-2.5)
    assert pe is None
    assert status == "NOT_MEANINGFUL"


def test_calculate_pe_ttm_positive():
    pe_ttm, status = FinancialMetricsCalculator.calculate_pe_ttm(price=1650.0, trailing_4q_eps=[14.0, 14.5, 14.5, 15.0])
    assert pe_ttm == round(1650.0 / 58.0, 4)
    assert status == "VALID"


def test_calculate_pe_ttm_negative_sum():
    pe_ttm, status = FinancialMetricsCalculator.calculate_pe_ttm(price=12.5, trailing_4q_eps=[-0.1, -0.1, -0.15, -0.15])
    assert pe_ttm is None
    assert status == "NOT_MEANINGFUL"


def test_calculate_pb_valid():
    pb, status = FinancialMetricsCalculator.calculate_pb(price=1650.0, book_value_per_share=180.0)
    assert pb == round(1650.0 / 180.0, 4)
    assert status == "VALID"


def test_calculate_pb_negative_book_value():
    pb, status = FinancialMetricsCalculator.calculate_pb(price=10.0, book_value_per_share=-2.0)
    assert pb is None
    assert status == "NOT_MEANINGFUL"


def test_calculate_dividend_yield_ttm():
    div_yield, status = FinancialMetricsCalculator.calculate_dividend_yield_ttm(price=1650.0, cash_dividends_12m=25.0)
    assert div_yield == round((25.0 / 1650.0) * 100.0, 4)
    assert status == "VALID"
