"""
fundamental_data.py — Canonical Fundamental Data Contract with Data Trust & Provenance fields.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class MetricProvenance(str, Enum):
    PROVIDER_REPORTED = "PROVIDER_REPORTED"
    DERIVED = "DERIVED"
    SYSTEM_CALCULATED = "SYSTEM_CALCULATED"
    CURRENT_ONLY = "CURRENT_ONLY"
    NOT_PIT_VERIFIED = "NOT_PIT_VERIFIED"
    UNAVAILABLE = "UNAVAILABLE"


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
    
    provenance: MetricProvenance = MetricProvenance.SYSTEM_CALCULATED
    quality_status: str = "VALID"      # "VALID", "INVALID", "SUSPECT", "MISSING"

    # Temporal & Provider Provenance metadata
    provider: str = "tushare_pro"
    provider_field: Optional[str] = None
    provider_timestamp: Optional[datetime] = None
    available_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    as_of: Optional[datetime] = None
