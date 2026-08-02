"""
fundamental_data.py — Canonical Fundamental Data Contract with Data Trust fields.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FundamentalDataContract:
    symbol: str               # "600519.SH"
    trade_date: str           # "YYYY-MM-DD"
    report_date: str          # Period date e.g., "2025-12-31"
    announcement_date: str    # Point-in-time publication date e.g., "2026-03-31"
    currency: str             # "CNY"
    
    # Financial Statement Line Items
    revenue: Optional[float]
    net_income: Optional[float]
    eps_annual: Optional[float]
    eps_ttm: Optional[float]
    book_value_per_share: Optional[float]
    operating_cash_flow: Optional[float]
    shares_outstanding: float
    market_cap: float
    
    # Financial Ratios & Valuation
    pe_lyr: Optional[float]           # PE Last Year Reported
    pe_ttm: Optional[float]           # PE Trailing Twelve Months
    pe_ttm_status: str                # "VALID", "NOT_MEANINGFUL", "UNAVAILABLE"
    pb: Optional[float]               # Price-to-Book
    pb_status: str                    # "VALID", "UNAVAILABLE"
    dividend_yield_ttm: Optional[float] # Trailing Dividend Yield
    dividend_yield_status: str        # "VALID", "UNAVAILABLE"
    roe: Optional[float]
    
    quality_status: str               # "VALID", "INVALID", "SUSPECT", "MISSING"
