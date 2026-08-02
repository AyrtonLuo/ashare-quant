"""
calculator.py — Independent Deterministic Financial Metrics Calculation Engine.
Calculates PE, PE-TTM, PB, Dividend Yield, and EPS with strict negative/missing value policies.
"""

from typing import Tuple, Optional


class FinancialMetricsCalculator:
    """Independent calculation engine ensuring zero reliance on unverified provider metrics."""

    @staticmethod
    def calculate_pe_lyr(price: float, eps_annual: Optional[float]) -> Tuple[Optional[float], str]:
        """
        Calculates Price-to-Earnings Ratio (Last Year Reported).
        Rules:
        - If eps_annual is None or <= 0: Returns (None, "NOT_MEANINGFUL")
        """
        if price <= 0:
            return None, "INVALID_PRICE"
        if eps_annual is None:
            return None, "MISSING_EPS"
        if eps_annual <= 0:
            return None, "NOT_MEANINGFUL"
        
        return round(price / eps_annual, 4), "VALID"

    @staticmethod
    def calculate_pe_ttm(price: float, trailing_4q_eps: Optional[list]) -> Tuple[Optional[float], str]:
        """
        Calculates Price-to-Earnings Trailing Twelve Months (PE-TTM).
        trailing_4q_eps: List of EPS for the past 4 consecutive quarters e.g., [Q1, Q2, Q3, Q4].
        """
        if price <= 0:
            return None, "INVALID_PRICE"
        if not trailing_4q_eps or len(trailing_4q_eps) != 4 or any(e is None for e in trailing_4q_eps):
            return None, "INCOMPLETE_TTM_QUARTERS"

        eps_ttm = sum(trailing_4q_eps)
        if eps_ttm <= 0:
            return None, "NOT_MEANINGFUL"

        return round(price / eps_ttm, 4), "VALID"

    @staticmethod
    def calculate_pb(price: float, book_value_per_share: Optional[float]) -> Tuple[Optional[float], str]:
        """
        Calculates Price-to-Book Ratio (PB).
        """
        if price <= 0:
            return None, "INVALID_PRICE"
        if book_value_per_share is None:
            return None, "MISSING_BOOK_VALUE"
        if book_value_per_share <= 0:
            return None, "NOT_MEANINGFUL"

        return round(price / book_value_per_share, 4), "VALID"

    @staticmethod
    def calculate_dividend_yield_ttm(
        price: float, cash_dividends_12m: float
    ) -> Tuple[Optional[float], str]:
        """
        Calculates Trailing 12-Month Dividend Yield.
        """
        if price <= 0:
            return None, "INVALID_PRICE"
        if cash_dividends_12m < 0:
            return None, "INVALID_DIVIDEND"
        
        dividend_yield = (cash_dividends_12m / price) * 100.0
        return round(dividend_yield, 4), "VALID"
